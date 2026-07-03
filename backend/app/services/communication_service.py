import uuid
import re
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.activity import Activity
from app.models.note import Note
from app.models.communication import CommunicationTemplate, CommunicationFlag
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

CHANNELS = ("Call", "SMS", "WhatsApp", "Email")
ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "csv", "xlsx", "docx"}


class CommunicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _scope(self, q, actor: User, model):
        if not self._privileged(actor):
            q = q.filter(or_(model.assigned_user_id == actor.id, model.created_by == actor.id))
        return q

    # ---------- Logging ----------
    async def log(self, actor: User, data: dict) -> dict:
        channel = data["channel"]
        if channel == "Note":
            note = Note(organization_id=actor.organization_id, content=data.get("body") or data["subject"],
                        lead_id=data.get("lead_id"), contact_id=data.get("contact_id"),
                        company_id=data.get("company_id"), created_by=actor.id)
            self.db.add(note)
            await self.db.flush()
            await self.db.refresh(note)
            return self._note_item(note, actor_name=None)

        if channel not in CHANNELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid channel. Allowed: {list(CHANNELS) + ['Note']}")
        if not (data.get("lead_id") or data.get("contact_id") or data.get("company_id")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link the communication to a lead, contact, or company")

        act = Activity(
            organization_id=actor.organization_id, activity_type=channel, subject=data["subject"],
            description=data.get("body"), status="Completed",
            assigned_user_id=actor.id, created_by=actor.id,
            lead_id=data.get("lead_id"), contact_id=data.get("contact_id"), company_id=data.get("company_id"),
            call_direction=data.get("direction", "OUTBOUND"), attachments=data.get("attachments"),
        )
        if data.get("occurred_at"):
            act.created_at = data["occurred_at"]
        self.db.add(act)
        await self.db.flush()

        # optional real email send (reuses the existing email service)
        if channel == "Email" and data.get("send_email") and data.get("to_email"):
            try:
                from app.services.email_service import send_email
                send_email(data["to_email"], data["subject"], "generic_message", {"body": data.get("body") or ""})
            except Exception:
                pass  # logging still succeeds even if delivery fails

        # Outbound messages are inherently "read" for the sender; inbound stay unread until actioned.
        outbound = act.call_direction != "INBOUND"
        if outbound:
            self.db.add(CommunicationFlag(organization_id=actor.organization_id, user_id=actor.id, activity_id=act.id,
                                          is_read=True, read_at=datetime.now(timezone.utc)))
        await self.db.flush()

        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="COMMUNICATION_LOGGED", resource_type="communication", resource_id=str(act.id),
                                   action_metadata={"channel": channel, "direction": act.call_direction})

        # Manually logged calls linked to a lead fire call_logged workflow rules too
        if channel == "Call" and act.lead_id:
            from app.models.lead import Lead
            from app.services.workflow_service import WorkflowService
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == act.lead_id, Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False))).scalars().first()
            if lead:
                await WorkflowService(self.db).run("call_logged", lead, actor)
        return self._activity_item(act, actor_name=f"{actor.first_name or ''} {actor.last_name or ''}".strip() or actor.email,
                                   is_read=outbound, is_pinned=False)

    # ---------- Feed ----------
    async def feed(self, actor: User, lead_id=None, contact_id=None, company_id=None, channel=None,
                   direction=None, search=None, unread_only=False, pinned_only=False,
                   include_notes=True, date_from=None, date_to=None, skip=0, limit=100) -> list[dict]:
        q = select(Activity).filter(Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
                                    Activity.activity_type.in_(CHANNELS))
        q = self._scope(q, actor, Activity)
        if lead_id:
            q = q.filter(Activity.lead_id == lead_id)
        if contact_id:
            q = q.filter(Activity.contact_id == contact_id)
        if company_id:
            q = q.filter(Activity.company_id == company_id)
        if channel and channel != "Note":
            q = q.filter(Activity.activity_type == channel)
        if direction:
            q = q.filter(Activity.call_direction == direction)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Activity.subject.ilike(s), Activity.description.ilike(s)))
        q = q.order_by(Activity.created_at.desc())
        acts = list((await self.db.execute(q)).scalars().all())

        flags = await self._flags_for(actor, [a.id for a in acts])
        actor_ids = {a.assigned_user_id or a.created_by for a in acts if (a.assigned_user_id or a.created_by)}
        names = await self._names(actor_ids)

        items = []
        for a in acts:
            fl = flags.get(a.id)
            read = (a.call_direction != "INBOUND") or (fl and fl.is_read)
            pinned = bool(fl and fl.is_pinned)
            if unread_only and read:
                continue
            if pinned_only and not pinned:
                continue
            uid = a.assigned_user_id or a.created_by
            items.append(self._activity_item(a, actor_name=names.get(uid), is_read=bool(read), is_pinned=pinned))

        # internal notes
        if include_notes and (channel is None or channel == "Note") and not unread_only and not pinned_only:
            nq = select(Note).filter(Note.organization_id == actor.organization_id, Note.is_deleted == False)
            nq = self._scope_notes(nq, actor)
            if lead_id:
                nq = nq.filter(Note.lead_id == lead_id)
            if contact_id:
                nq = nq.filter(Note.contact_id == contact_id)
            if company_id:
                nq = nq.filter(Note.company_id == company_id)
            if search:
                nq = nq.filter(Note.content.ilike(f"%{search}%"))
            notes = list((await self.db.execute(nq.order_by(Note.created_at.desc()))).scalars().all())
            nnames = await self._names({n.created_by for n in notes if n.created_by})
            for n in notes:
                items.append(self._note_item(n, actor_name=nnames.get(n.created_by)))

        # pinned first, then newest
        items.sort(key=lambda i: (not i["is_pinned"], -i["timestamp"].timestamp()))
        return items[skip:skip + limit]

    def _scope_notes(self, q, actor: User):
        if not self._privileged(actor):
            q = q.filter(Note.created_by == actor.id)
        return q

    # ---------- Conversations (sidebar) ----------
    async def conversations(self, actor: User, search=None, limit=50) -> list[dict]:
        q = select(Activity).filter(Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
                                    Activity.activity_type.in_(CHANNELS),
                                    or_(Activity.contact_id.isnot(None), Activity.company_id.isnot(None), Activity.lead_id.isnot(None)))
        q = self._scope(q, actor, Activity)
        q = q.order_by(Activity.created_at.desc()).limit(1000)
        acts = list((await self.db.execute(q)).scalars().all())

        flags = await self._flags_for(actor, [a.id for a in acts])
        convos: dict = {}
        for a in acts:
            if a.contact_id:
                key = ("contact", a.contact_id)
            elif a.company_id:
                key = ("company", a.company_id)
            else:
                key = ("lead", a.lead_id)
            c = convos.setdefault(key, {"entity_type": key[0], "entity_id": str(key[1]), "name": "",
                                        "last_channel": a.activity_type, "last_subject": a.subject, "last_at": a.created_at,
                                        "unread_count": 0, "total": 0, "pinned": False})
            c["total"] += 1
            fl = flags.get(a.id)
            if a.call_direction == "INBOUND" and not (fl and fl.is_read):
                c["unread_count"] += 1
            if fl and fl.is_pinned:
                c["pinned"] = True
        await self._resolve_convo_names(actor, convos)
        result = list(convos.values())
        if search:
            s = search.lower()
            result = [c for c in result if s in c["name"].lower()]
        result.sort(key=lambda c: (not c["pinned"], -c["last_at"].timestamp()))
        return result[:limit]

    async def _resolve_convo_names(self, actor: User, convos: dict):
        from app.models.contact import Contact
        from app.models.company import Company
        from app.models.lead import Lead
        by_type = {"contact": [], "company": [], "lead": []}
        for (etype, eid) in convos:
            by_type[etype].append(eid)
        names = {}
        if by_type["contact"]:
            r = await self.db.execute(select(Contact.id, Contact.first_name, Contact.last_name).filter(Contact.id.in_(by_type["contact"])))
            for cid, fn, ln in r.all():
                names[("contact", cid)] = f"{fn} {ln}".strip()
        if by_type["company"]:
            r = await self.db.execute(select(Company.id, Company.name).filter(Company.id.in_(by_type["company"])))
            for cid, nm in r.all():
                names[("company", cid)] = nm
        if by_type["lead"]:
            r = await self.db.execute(select(Lead.id, Lead.title).filter(Lead.id.in_(by_type["lead"])))
            for lid, ttl in r.all():
                names[("lead", lid)] = ttl
        for key, c in convos.items():
            c["name"] = names.get(key, "Unknown")

    # ---------- Read / pin ----------
    async def _upsert_flag(self, actor: User, activity_id: uuid.UUID) -> CommunicationFlag:
        res = await self.db.execute(select(CommunicationFlag).filter(
            CommunicationFlag.user_id == actor.id, CommunicationFlag.activity_id == activity_id))
        fl = res.scalars().first()
        if not fl:
            # ensure the activity exists in the org
            act = (await self.db.execute(select(Activity).filter(Activity.id == activity_id, Activity.organization_id == actor.organization_id))).scalars().first()
            if not act:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
            fl = CommunicationFlag(organization_id=actor.organization_id, user_id=actor.id, activity_id=activity_id)
            self.db.add(fl)
        return fl

    async def mark_read(self, actor: User, activity_id: uuid.UUID) -> None:
        fl = await self._upsert_flag(actor, activity_id)
        fl.is_read = True
        fl.read_at = datetime.now(timezone.utc)
        self.db.add(fl)
        await self.db.flush()

    async def mark_all_read(self, actor: User, contact_id=None, company_id=None, lead_id=None) -> int:
        q = select(Activity).filter(Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
                                    Activity.activity_type.in_(CHANNELS), Activity.call_direction == "INBOUND")
        q = self._scope(q, actor, Activity)
        if contact_id:
            q = q.filter(Activity.contact_id == contact_id)
        if company_id:
            q = q.filter(Activity.company_id == company_id)
        if lead_id:
            q = q.filter(Activity.lead_id == lead_id)
        acts = list((await self.db.execute(q)).scalars().all())
        n = 0
        for a in acts:
            fl = await self._upsert_flag(actor, a.id)
            if not fl.is_read:
                fl.is_read = True
                fl.read_at = datetime.now(timezone.utc)
                self.db.add(fl)
                n += 1
        await self.db.flush()
        return n

    async def toggle_pin(self, actor: User, activity_id: uuid.UUID) -> bool:
        fl = await self._upsert_flag(actor, activity_id)
        fl.is_pinned = not fl.is_pinned
        self.db.add(fl)
        await self.db.flush()
        return fl.is_pinned

    # ---------- Stats ----------
    async def stats(self, actor: User) -> dict:
        q = select(Activity).filter(Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
                                    Activity.activity_type.in_(CHANNELS))
        q = self._scope(q, actor, Activity)
        acts = list((await self.db.execute(q)).scalars().all())
        flags = await self._flags_for(actor, [a.id for a in acts])
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        by_channel: dict = {}
        by_dir: dict = {}
        unread = 0
        this_week = 0
        for a in acts:
            by_channel[a.activity_type] = by_channel.get(a.activity_type, 0) + 1
            d = a.call_direction or "OUTBOUND"
            by_dir[d] = by_dir.get(d, 0) + 1
            created = a.created_at if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc)
            if created >= week_ago:
                this_week += 1
            fl = flags.get(a.id)
            if a.call_direction == "INBOUND" and not (fl and fl.is_read):
                unread += 1
        return {
            "total": len(acts), "unread": unread, "this_week": this_week,
            "by_channel": [{"label": k, "count": v} for k, v in by_channel.items()],
            "by_direction": [{"label": k, "count": v} for k, v in by_dir.items()],
        }

    # ---------- Attachments ----------
    async def add_attachment(self, actor: User, activity_id: uuid.UUID, content: bytes, filename: str) -> dict:
        from app.core.storage import validate_and_sanitize_file, get_storage_provider
        act = await self._get_comm(actor, activity_id)
        try:
            sanitized, ext = validate_and_sanitize_file(content=content, filename=filename, allowed_extensions=ATTACHMENT_EXTENSIONS)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        url = await get_storage_provider().upload_file(content, sanitized)
        att = {"filename": filename, "stored_name": sanitized, "url": url, "size": len(content),
               "uploaded_by": str(actor.id), "uploaded_at": datetime.now(timezone.utc).isoformat()}
        existing = list(act.attachments or [])
        existing.append(att)
        act.attachments = existing
        self.db.add(act)
        await self.db.flush()
        return att

    async def list_attachments(self, actor: User, activity_id: uuid.UUID) -> list[dict]:
        act = await self._get_comm(actor, activity_id)
        return list(act.attachments or [])

    async def delete_attachment(self, actor: User, activity_id: uuid.UUID, stored_name: str) -> dict:
        from app.core.storage import get_storage_provider
        act = await self._get_comm(actor, activity_id)
        existing = list(act.attachments or [])
        target = next((a for a in existing if a.get("stored_name") == stored_name or a.get("filename") == stored_name), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        act.attachments = [a for a in existing if a is not target]
        self.db.add(act)
        await self.db.flush()
        try:
            await get_storage_provider().delete_file(target["url"])
        except Exception:
            pass
        return {"deleted": True}

    async def _get_comm(self, actor: User, activity_id: uuid.UUID) -> Activity:
        act = (await self.db.execute(select(Activity).filter(
            Activity.id == activity_id, Activity.organization_id == actor.organization_id, Activity.is_deleted == False))).scalars().first()
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
        return act

    # ---------- Templates ----------
    async def list_templates(self, actor: User) -> list[CommunicationTemplate]:
        # Composers only offer approved, active templates. The managed template
        # module (/templates) exposes drafts/pending for editing/approval.
        res = await self.db.execute(select(CommunicationTemplate).filter(
            CommunicationTemplate.organization_id == actor.organization_id, CommunicationTemplate.is_deleted == False,
            CommunicationTemplate.status == "approved", CommunicationTemplate.is_active == True).order_by(CommunicationTemplate.name.asc()))
        return list(res.scalars().all())

    async def create_template(self, actor: User, data: dict) -> CommunicationTemplate:
        t = CommunicationTemplate(organization_id=actor.organization_id, name=data["name"], channel=data.get("channel", "Email"),
                                  subject=data.get("subject"), body=data["body"], created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def _get_template(self, actor: User, template_id: uuid.UUID) -> CommunicationTemplate:
        t = (await self.db.execute(select(CommunicationTemplate).filter(
            CommunicationTemplate.id == template_id, CommunicationTemplate.organization_id == actor.organization_id, CommunicationTemplate.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        return t

    async def update_template(self, actor: User, template_id: uuid.UUID, data: dict) -> CommunicationTemplate:
        t = await self._get_template(actor, template_id)
        for k, v in data.items():
            setattr(t, k, v)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def delete_template(self, actor: User, template_id: uuid.UUID) -> None:
        t = await self._get_template(actor, template_id)
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    async def render_template(self, actor: User, template_id: uuid.UUID, data: dict) -> dict:
        t = await self._get_template(actor, template_id)
        ctx = {"first_name": "", "last_name": "", "full_name": "", "company": "",
               "owner": f"{actor.first_name or ''} {actor.last_name or ''}".strip() or actor.email, "email": ""}
        if data.get("contact_id"):
            from app.models.contact import Contact
            c = (await self.db.execute(select(Contact).filter(Contact.id == data["contact_id"], Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                ctx.update({"first_name": c.first_name or "", "last_name": c.last_name or "",
                            "full_name": f"{c.first_name or ''} {c.last_name or ''}".strip(), "email": c.email or ""})
        if data.get("company_id"):
            from app.models.company import Company
            comp = (await self.db.execute(select(Company).filter(Company.id == data["company_id"], Company.organization_id == actor.organization_id))).scalars().first()
            if comp:
                ctx["company"] = comp.name
        if data.get("lead_id"):
            from app.models.lead import Lead
            l = (await self.db.execute(select(Lead).filter(Lead.id == data["lead_id"], Lead.organization_id == actor.organization_id))).scalars().first()
            if l:
                ctx.setdefault("full_name", l.last_name or "")
                if not ctx["first_name"]:
                    ctx["first_name"] = l.first_name or ""
                if not ctx["company"]:
                    ctx["company"] = l.company_name or ""

        def sub(text: str | None) -> str | None:
            if not text:
                return text
            return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text)

        # Rendering a template for use counts as usage (drives the template reports).
        from app.services.template_service import TemplateService
        await TemplateService.mark_used(self.db, t.id)

        return {"subject": sub(t.subject), "body": sub(t.body)}

    # ---------- helpers ----------
    async def _flags_for(self, actor: User, activity_ids: list) -> dict:
        if not activity_ids:
            return {}
        res = await self.db.execute(select(CommunicationFlag).filter(
            CommunicationFlag.user_id == actor.id, CommunicationFlag.activity_id.in_(activity_ids)))
        return {f.activity_id: f for f in res.scalars().all()}

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    def _activity_item(self, a: Activity, actor_name, is_read, is_pinned) -> dict:
        return {"id": str(a.id), "channel": a.activity_type, "direction": a.call_direction, "subject": a.subject,
                "body": a.description, "status": a.status, "timestamp": a.created_at,
                "actor_user_id": str(a.assigned_user_id or a.created_by) if (a.assigned_user_id or a.created_by) else None,
                "actor_name": actor_name, "lead_id": str(a.lead_id) if a.lead_id else None,
                "contact_id": str(a.contact_id) if a.contact_id else None, "company_id": str(a.company_id) if a.company_id else None,
                "recording_url": a.recording_url, "attachments": a.attachments, "is_read": is_read, "is_pinned": is_pinned, "internal": False}

    def _note_item(self, n: Note, actor_name) -> dict:
        return {"id": str(n.id), "channel": "Note", "direction": None, "subject": "Internal note", "body": n.content,
                "status": "Completed", "timestamp": n.created_at,
                "actor_user_id": str(n.created_by) if n.created_by else None, "actor_name": actor_name,
                "lead_id": str(n.lead_id) if n.lead_id else None, "contact_id": str(n.contact_id) if n.contact_id else None,
                "company_id": str(n.company_id) if n.company_id else None, "recording_url": None, "attachments": None,
                "is_read": True, "is_pinned": False, "internal": True}

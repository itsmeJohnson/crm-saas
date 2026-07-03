"""Email module service.

Emails are Activity rows (activity_type='Email') so they flow through the
Communication Center feed and customer timeline unchanged. This service owns the
mailbox lifecycle: per-org SMTP/IMAP/OAuth config, threaded send/reply/forward,
drafts, IMAP inbound fetch, and open/click tracking. Distinct from the global
transactional `email_service.send_email` used for billing/auth notifications.
"""
import re
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.communication import CommunicationFlag, CommunicationTemplate
from app.models.email_settings import EmailSettings
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.email_providers import get_transport, get_fetcher

_LINK_RE = re.compile(r'href=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EmailModuleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------- Settings ----------
    async def get_settings(self, actor: User, create: bool = True) -> EmailSettings | None:
        res = await self.db.execute(select(EmailSettings).filter(
            EmailSettings.organization_id == actor.organization_id, EmailSettings.is_deleted == False))
        s = res.scalars().first()
        if not s and create:
            s = EmailSettings(organization_id=actor.organization_id, provider="mock", auth_method="smtp",
                              from_email=actor.email, tracking_enabled=True)
            self.db.add(s)
            await self.db.flush()
            await self.db.refresh(s)
        return s

    async def update_settings(self, actor: User, data: dict) -> EmailSettings:
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can change email settings.")
        s = await self.get_settings(actor, create=True)
        for k in ("auth_method", "from_email", "from_name", "smtp_host", "smtp_port", "smtp_username",
                  "smtp_password", "smtp_use_tls", "imap_host", "imap_port", "imap_username", "imap_password",
                  "imap_use_ssl", "tracking_enabled", "tracking_base_url", "provider", "is_active"):
            if k in data and data[k] is not None:
                setattr(s, k, data[k])
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return s

    async def oauth_connect(self, actor: User, data: dict) -> EmailSettings:
        """Store OAuth tokens obtained from Google/Microsoft and flip auth_method.
        The redirect/exchange happens client-side or via the provider console; this
        persists the resulting tokens so send/fetch can authenticate via XOAUTH2."""
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can connect a mailbox.")
        s = await self.get_settings(actor, create=True)
        provider = data.get("provider", "google")
        s.auth_method = "oauth_microsoft" if provider == "microsoft" else "oauth_google"
        s.oauth_email = data.get("email")
        s.oauth_access_token = data.get("access_token")
        s.oauth_refresh_token = data.get("refresh_token")
        if data.get("email") and not s.from_email:
            s.from_email = data["email"]
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return s

    # ---------- Tracking helpers ----------
    def _tracking_base(self, settings_row) -> str:
        base = (settings_row.tracking_base_url if settings_row else None) or ""
        return base.rstrip("/")

    def _inject_tracking(self, html: str, tracking_id: str, base: str, enabled: bool) -> str:
        if not enabled or not base:
            return html
        # Rewrite links for click tracking
        def repl(m):
            url = m.group(1)
            return f'href="{base}/api/v1/email/track/click/{tracking_id}?u={quote(url, safe="")}"'
        tracked = _LINK_RE.sub(repl, html or "")
        # Append a 1x1 open-tracking pixel
        pixel = (f'<img src="{base}/api/v1/email/track/open/{tracking_id}" width="1" height="1" '
                 f'alt="" style="display:none" />')
        return (tracked or "") + pixel

    # ---------- Recipient resolution ----------
    async def _resolve_to(self, actor: User, data: dict) -> tuple[str, dict]:
        links = {"lead_id": data.get("lead_id"), "contact_id": data.get("contact_id"),
                 "company_id": data.get("company_id")}
        to = (data.get("to") or "").strip()
        if not to and data.get("lead_id"):
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == data["lead_id"], Lead.organization_id == actor.organization_id))).scalars().first()
            if lead:
                to = (lead.email or "").strip()
        if not to and data.get("contact_id"):
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == data["contact_id"], Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                to = (c.email or "").strip()
        return to, links

    # ---------- Send ----------
    async def send(self, actor: User, data: dict, *, _draft_activity: Activity | None = None) -> Activity:
        subject = (data.get("subject") or "").strip()
        if not subject:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject is required.")
        body = data.get("body") or ""
        settings_row = await self.get_settings(actor, create=True)
        to, links = await self._resolve_to(actor, data)
        if not to:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No recipient: provide 'to' or a lead/contact with an email.")
        cc = data.get("cc") or ""
        thread_id = data.get("thread_id") or uuid.uuid4()
        in_reply_to = data.get("in_reply_to")
        tracking_id = secrets.token_urlsafe(16)
        from_email = (settings_row.from_email if settings_row else None) or actor.email
        from_name = (settings_row.from_name if settings_row else None) or f"{actor.first_name or ''} {actor.last_name or ''}".strip()
        from_addr = f"{from_name} <{from_email}>" if from_name else from_email

        html = self._inject_tracking(body, tracking_id, self._tracking_base(settings_row),
                                     bool(settings_row and settings_row.tracking_enabled))
        transport = get_transport(settings_row)
        result = transport.send(
            from_addr=from_addr, to_addrs=[a.strip() for a in to.split(",") if a.strip()],
            cc_addrs=[a.strip() for a in cc.split(",") if a.strip()], subject=subject,
            html_body=html, in_reply_to=in_reply_to, attachments=data.get("attachments"))

        if _draft_activity is not None:
            act = _draft_activity
            act.is_draft = False
        else:
            act = Activity(organization_id=actor.organization_id, activity_type="Email",
                           assigned_user_id=actor.id, created_by=actor.id)
        act.subject = subject
        act.description = body
        act.call_direction = "OUTBOUND"
        act.status = "Completed" if result.status != "failed" else "Failed"
        act.lead_id = links["lead_id"]
        act.contact_id = links["contact_id"]
        act.company_id = links["company_id"]
        act.email_from = from_email
        act.email_to = to
        act.email_cc = cc or None
        act.email_message_id = result.message_id
        act.email_in_reply_to = in_reply_to
        act.email_thread_id = thread_id
        act.email_status = "sent" if result.status != "failed" else "failed"
        act.email_tracking_id = tracking_id
        act.attachments = data.get("attachments")
        self.db.add(act)
        await self.db.flush()

        # de-dup the read flag when sending a previously-saved draft
        existing_flag = (await self.db.execute(select(CommunicationFlag).filter(
            CommunicationFlag.user_id == actor.id, CommunicationFlag.activity_id == act.id))).scalars().first()
        if not existing_flag:
            self.db.add(CommunicationFlag(organization_id=actor.organization_id, user_id=actor.id,
                                          activity_id=act.id, is_read=True, read_at=_now()))
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="EMAIL_SENT", resource_type="communication", resource_id=str(act.id),
                                   action_metadata={"to": to, "status": result.status, "thread": str(thread_id)})
        return act

    async def reply(self, actor: User, activity_id: uuid.UUID, data: dict) -> Activity:
        orig = await self._get_email(actor, activity_id)
        # reply goes back to the counterparty
        to = orig.email_from if orig.call_direction == "INBOUND" else orig.email_to
        subject = orig.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        return await self.send(actor, {
            "to": data.get("to") or to, "cc": data.get("cc"), "subject": subject, "body": data.get("body") or "",
            "thread_id": orig.email_thread_id or uuid.uuid4(), "in_reply_to": orig.email_message_id,
            "lead_id": orig.lead_id, "contact_id": orig.contact_id, "company_id": orig.company_id,
            "attachments": data.get("attachments")})

    async def forward(self, actor: User, activity_id: uuid.UUID, data: dict) -> Activity:
        orig = await self._get_email(actor, activity_id)
        to = (data.get("to") or "").strip()
        if not to:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A recipient is required to forward.")
        subject = orig.subject or ""
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        quoted = (f"{data.get('body') or ''}<hr/><blockquote>{orig.description or ''}</blockquote>")
        return await self.send(actor, {
            "to": to, "cc": data.get("cc"), "subject": subject, "body": quoted,
            "lead_id": orig.lead_id, "contact_id": orig.contact_id, "company_id": orig.company_id,
            "attachments": orig.attachments})

    # ---------- Drafts ----------
    async def create_draft(self, actor: User, data: dict) -> Activity:
        to, links = await self._resolve_to(actor, data)
        act = Activity(organization_id=actor.organization_id, activity_type="Email",
                       subject=data.get("subject") or "(no subject)", description=data.get("body") or "",
                       status="Planned", call_direction="OUTBOUND", assigned_user_id=actor.id, created_by=actor.id,
                       lead_id=links["lead_id"], contact_id=links["contact_id"], company_id=links["company_id"],
                       email_to=to or None, email_cc=data.get("cc"), email_status="draft", is_draft=True,
                       attachments=data.get("attachments"))
        self.db.add(act)
        await self.db.flush()
        return act

    async def update_draft(self, actor: User, activity_id: uuid.UUID, data: dict) -> Activity:
        act = await self._get_email(actor, activity_id)
        if not act.is_draft:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be edited.")
        if "subject" in data and data["subject"] is not None:
            act.subject = data["subject"]
        if "body" in data and data["body"] is not None:
            act.description = data["body"]
        if "cc" in data:
            act.email_cc = data["cc"]
        if data.get("to") is not None:
            act.email_to = data["to"]
        for k in ("lead_id", "contact_id", "company_id"):
            if k in data and data[k] is not None:
                setattr(act, k, data[k])
        self.db.add(act)
        await self.db.flush()
        return act

    async def send_draft(self, actor: User, activity_id: uuid.UUID) -> Activity:
        act = await self._get_email(actor, activity_id)
        if not act.is_draft:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a draft.")
        return await self.send(actor, {
            "to": act.email_to, "cc": act.email_cc, "subject": act.subject, "body": act.description,
            "lead_id": act.lead_id, "contact_id": act.contact_id, "company_id": act.company_id,
            "attachments": act.attachments}, _draft_activity=act)

    async def delete_draft(self, actor: User, activity_id: uuid.UUID) -> None:
        act = await self._get_email(actor, activity_id)
        if not act.is_draft:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be deleted here.")
        act.is_deleted = True
        self.db.add(act)
        await self.db.flush()

    # ---------- Inbound (IMAP) ----------
    async def _fallback_creator(self, org_id: uuid.UUID, preferred: uuid.UUID | None) -> uuid.UUID:
        if preferred:
            return preferred
        admin = (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.role == "OrgAdmin", User.is_active == True,
            User.is_deleted == False).limit(1))).scalar()
        if admin:
            return admin
        return (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.is_active == True, User.is_deleted == False).limit(1))).scalar()

    async def ingest_inbound(self, org_id: uuid.UUID, from_addr: str, to_addr: str, subject: str,
                             body: str, message_id: str | None, in_reply_to: str | None) -> Activity | None:
        from_addr = (from_addr or "").strip().lower()
        if not from_addr:
            return None
        lead = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False,
            func.lower(Lead.email) == from_addr))).scalars().first()
        contact = None
        if not lead:
            contact = (await self.db.execute(select(Contact).filter(
                Contact.organization_id == org_id, Contact.is_deleted == False,
                func.lower(Contact.email) == from_addr))).scalars().first()

        owner = None
        if lead:
            owner = lead.assigned_user_id or lead.created_by
        elif contact:
            owner = contact.assigned_user_id or contact.created_by

        # Thread by In-Reply-To → the message it replies to
        thread_id = None
        if in_reply_to:
            parent = (await self.db.execute(select(Activity).filter(
                Activity.organization_id == org_id, Activity.activity_type == "Email",
                Activity.email_message_id == in_reply_to))).scalars().first()
            if parent:
                thread_id = parent.email_thread_id
        thread_id = thread_id or uuid.uuid4()

        creator = await self._fallback_creator(org_id, owner)
        act = Activity(organization_id=org_id, activity_type="Email",
                       subject=subject or "(no subject)", description=body or "", status="Completed",
                       call_direction="INBOUND", assigned_user_id=owner, created_by=creator,
                       lead_id=lead.id if lead else None, contact_id=contact.id if contact else None,
                       email_from=from_addr, email_to=to_addr, email_message_id=message_id,
                       email_in_reply_to=in_reply_to, email_thread_id=thread_id, email_status="received")
        self.db.add(act)
        await self.db.flush()

        if owner:
            who = (lead.title if lead else (f"{contact.first_name or ''} {contact.last_name or ''}".strip() if contact else from_addr))
            await self.notifier.create_notification(
                organization_id=org_id, user_id=owner, category="email",
                title="New email received", body=f"Email from {who or from_addr}: {subject[:80]}",
                link_url="/email", action_metadata={"activity_id": str(act.id), "from": from_addr})

        if lead and owner:
            wf_owner = await self.db.get(User, owner)
            if wf_owner:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(self.db).run("email_received", lead, wf_owner)
        return act

    async def sync_inbox(self, org_id: uuid.UUID) -> int:
        """Pull UNSEEN mail via IMAP and record it. Returns count ingested."""
        settings_row = (await self.db.execute(select(EmailSettings).filter(
            EmailSettings.organization_id == org_id, EmailSettings.is_deleted == False))).scalars().first()
        if not settings_row or not settings_row.is_active:
            return 0
        fetcher = get_fetcher(settings_row)
        fetched = fetcher.fetch(limit=50)
        n = 0
        for fe in fetched:
            if fe.message_id:
                dup = (await self.db.execute(select(Activity.id).filter(
                    Activity.organization_id == org_id, Activity.activity_type == "Email",
                    Activity.email_message_id == fe.message_id))).scalar()
                if dup:
                    continue
            if await self.ingest_inbound(org_id, fe.from_addr, fe.to_addr, fe.subject, fe.body,
                                         fe.message_id, fe.in_reply_to):
                n += 1
        settings_row.last_synced_at = _now()
        self.db.add(settings_row)
        await self.db.flush()
        return n

    # ---------- Tracking record ----------
    async def record_open(self, tracking_id: str) -> None:
        act = (await self.db.execute(select(Activity).filter(
            Activity.email_tracking_id == tracking_id, Activity.activity_type == "Email"))).scalars().first()
        if act:
            act.email_open_count = (act.email_open_count or 0) + 1
            if not act.email_opened_at:
                act.email_opened_at = _now()
            self.db.add(act)
            await self.db.flush()

    async def record_click(self, tracking_id: str) -> None:
        act = (await self.db.execute(select(Activity).filter(
            Activity.email_tracking_id == tracking_id, Activity.activity_type == "Email"))).scalars().first()
        if act:
            act.email_click_count = (act.email_click_count or 0) + 1
            if not act.email_clicked_at:
                act.email_clicked_at = _now()
            # a click implies an open
            if not act.email_opened_at:
                act.email_opened_at = _now()
                act.email_open_count = (act.email_open_count or 0) + 1
            self.db.add(act)
            await self.db.flush()

    # ---------- Queries ----------
    def _scope(self, q, actor: User):
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        return q

    async def _get_email(self, actor: User, activity_id: uuid.UUID) -> Activity:
        q = select(Activity).filter(
            Activity.id == activity_id, Activity.organization_id == actor.organization_id,
            Activity.is_deleted == False, Activity.activity_type == "Email")
        act = (await self.db.execute(self._scope(q, actor))).scalars().first()
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
        return act

    async def messages(self, actor: User, folder="inbox", search=None, skip=0, limit=50) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "Email")
        q = self._scope(q, actor)
        if folder == "inbox":
            q = q.filter(Activity.call_direction == "INBOUND")
        elif folder == "sent":
            q = q.filter(Activity.call_direction == "OUTBOUND", Activity.is_draft == False)
        elif folder == "drafts":
            q = q.filter(Activity.is_draft == True)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Activity.subject.ilike(s), Activity.description.ilike(s),
                             Activity.email_from.ilike(s), Activity.email_to.ilike(s)))
        acts = list((await self.db.execute(q.order_by(Activity.created_at.desc()))).scalars().all())
        total = len(acts)
        acts = acts[skip:skip + limit]
        names = await self._names({a.assigned_user_id or a.created_by for a in acts})
        return {"items": [self._item(a, names) for a in acts], "total": total}

    async def threads(self, actor: User, search=None, skip=0, limit=50) -> list[dict]:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "Email", Activity.is_draft == False,
            Activity.email_thread_id.isnot(None))
        q = self._scope(q, actor)
        acts = list((await self.db.execute(q.order_by(Activity.created_at.desc()))).scalars().all())
        grouped: dict = {}
        for a in acts:
            g = grouped.setdefault(a.email_thread_id, {
                "thread_id": str(a.email_thread_id), "subject": a.subject, "last_at": a.created_at,
                "count": 0, "last_direction": a.call_direction, "opened": False, "clicked": False,
                "lead_id": str(a.lead_id) if a.lead_id else None,
                "contact_id": str(a.contact_id) if a.contact_id else None})
            g["count"] += 1
            if a.email_open_count:
                g["opened"] = True
            if a.email_click_count:
                g["clicked"] = True
        result = list(grouped.values())
        if search:
            sl = search.lower()
            result = [g for g in result if sl in (g["subject"] or "").lower()]
        result.sort(key=lambda g: g["last_at"].timestamp(), reverse=True)
        return result[skip:skip + limit]

    async def thread_detail(self, actor: User, thread_id: uuid.UUID) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "Email", Activity.email_thread_id == thread_id)
        q = self._scope(q, actor)
        acts = list((await self.db.execute(q.order_by(Activity.created_at.asc()))).scalars().all())
        if not acts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        names = await self._names({a.assigned_user_id or a.created_by for a in acts})
        return {"thread_id": str(thread_id), "subject": acts[-1].subject,
                "messages": [self._item(a, names) for a in acts]}

    def _item(self, a: Activity, names: dict) -> dict:
        uid = a.assigned_user_id or a.created_by
        return {
            "id": str(a.id), "direction": a.call_direction, "subject": a.subject, "body": a.description,
            "email_from": a.email_from, "email_to": a.email_to, "email_cc": a.email_cc,
            "status": a.email_status, "is_draft": a.is_draft,
            "open_count": a.email_open_count or 0, "click_count": a.email_click_count or 0,
            "opened_at": a.email_opened_at, "clicked_at": a.email_clicked_at,
            "thread_id": str(a.email_thread_id) if a.email_thread_id else None,
            "attachments": a.attachments, "timestamp": a.created_at,
            "agent_id": str(uid) if uid else None, "agent_name": names.get(uid),
            "lead_id": str(a.lead_id) if a.lead_id else None,
            "contact_id": str(a.contact_id) if a.contact_id else None,
            "company_id": str(a.company_id) if a.company_id else None,
        }

    async def reports(self, actor: User, date_from=None, date_to=None) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "Email")
        q = self._scope(q, actor)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        acts = list((await self.db.execute(q)).scalars().all())
        by_status: dict = {}
        by_direction: dict = {}
        by_day: dict = {}
        sent = opened = clicked = failed = drafts = inbound = 0
        for a in acts:
            st = a.email_status or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
            d = a.call_direction or "OUTBOUND"
            by_direction[d] = by_direction.get(d, 0) + 1
            by_day[a.created_at.date().isoformat()] = by_day.get(a.created_at.date().isoformat(), 0) + 1
            if a.is_draft:
                drafts += 1
            elif d == "INBOUND":
                inbound += 1
            elif st == "sent":
                sent += 1
                if a.email_open_count:
                    opened += 1
                if a.email_click_count:
                    clicked += 1
            elif st == "failed":
                failed += 1
        return {
            "total": len(acts), "sent": sent, "inbound": inbound, "drafts": drafts, "failed": failed,
            "opened": opened, "clicked": clicked,
            "open_rate": round(opened * 100 / sent, 1) if sent else 0.0,
            "click_rate": round(clicked * 100 / sent, 1) if sent else 0.0,
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
            "by_day": [{"label": day, "count": c} for day, c in sorted(by_day.items())],
        }

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

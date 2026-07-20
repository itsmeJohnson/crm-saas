"""Communication Template module service.

Owns the managed lifecycle of communication_templates on top of the basic
CRUD in CommunicationService: categories, an approval workflow
(draft→pending_approval→approved/rejected), immutable version history, preview
with sample or real entity data, cross-channel test sends, usage tracking, and
reporting. Reuses the existing communication_templates table so the messaging
composers keep reading the same rows.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone, date
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.communication import CommunicationTemplate, CommunicationTemplateVersion
from app.services.audit_service import AuditService

CHANNELS = ("Email", "SMS", "WhatsApp", "Call")
STATUSES = ("draft", "pending_approval", "approved", "rejected")

# Dynamic fields available in template bodies/subjects as {{placeholder}}.
VARIABLES = [
    {"key": "first_name", "label": "First name"},
    {"key": "last_name", "label": "Last name"},
    {"key": "full_name", "label": "Full name"},
    {"key": "email", "label": "Recipient email"},
    {"key": "phone", "label": "Recipient phone"},
    {"key": "company", "label": "Company name"},
    {"key": "job_title", "label": "Job title"},
    {"key": "owner", "label": "Sending user's name"},
    {"key": "owner_email", "label": "Sending user's email"},
    {"key": "date", "label": "Today's date"},
]

_SUB_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

_SAMPLE = {
    "first_name": "Jane", "last_name": "Doe", "full_name": "Jane Doe",
    "email": "jane.doe@example.com", "phone": "+15551234567", "company": "Acme Corp",
    "job_title": "VP Sales", "date": date.today().isoformat(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------- Rendering / preview ----------
    def _substitute(self, text: str | None, ctx: dict) -> str | None:
        if not text:
            return text
        return _SUB_RE.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), text)

    async def _entity_context(self, actor: User, data: dict) -> dict:
        ctx = {k: "" for k in ("first_name", "last_name", "full_name", "email", "phone", "company", "job_title")}
        ctx["owner"] = f"{actor.first_name or ''} {actor.last_name or ''}".strip() or actor.email
        ctx["owner_email"] = actor.email
        ctx["date"] = date.today().isoformat()
        if data.get("contact_id"):
            from app.models.contact import Contact
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == data["contact_id"], Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                ctx.update({"first_name": c.first_name or "", "last_name": c.last_name or "",
                            "full_name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
                            "email": c.email or "", "phone": c.phone or "", "job_title": getattr(c, "job_title", "") or ""})
        if data.get("lead_id"):
            from app.models.lead import Lead
            l = (await self.db.execute(select(Lead).filter(
                Lead.id == data["lead_id"], Lead.organization_id == actor.organization_id))).scalars().first()
            if l:
                if not ctx["first_name"]:
                    ctx["first_name"] = l.first_name or ""
                if not ctx["last_name"]:
                    ctx["last_name"] = l.last_name or ""
                ctx["full_name"] = ctx["full_name"] or f"{l.first_name or ''} {l.last_name or ''}".strip()
                ctx["email"] = ctx["email"] or (l.email or "")
                ctx["phone"] = ctx["phone"] or (l.phone or "")
                ctx["company"] = ctx["company"] or (l.company_name or "")
        if data.get("company_id"):
            from app.models.company import Company
            comp = (await self.db.execute(select(Company).filter(
                Company.id == data["company_id"], Company.organization_id == actor.organization_id))).scalars().first()
            if comp:
                ctx["company"] = comp.name
        return ctx

    async def preview(self, actor: User, template_id: uuid.UUID, data: dict) -> dict:
        t = await self._get(actor, template_id)
        if data.get("contact_id") or data.get("lead_id") or data.get("company_id"):
            ctx = await self._entity_context(actor, data)
        else:
            ctx = dict(_SAMPLE)
            ctx["owner"] = f"{actor.first_name or ''} {actor.last_name or ''}".strip() or actor.email
            ctx["owner_email"] = actor.email
        return {"channel": t.channel, "subject": self._substitute(t.subject, ctx), "body": self._substitute(t.body, ctx)}

    # ---------- CRUD ----------
    async def list(self, actor: User, channel=None, category=None, status_filter=None, search=None,
                   skip=0, limit=100) -> list[CommunicationTemplate]:
        q = select(CommunicationTemplate).filter(
            CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.is_deleted == False)
        if channel:
            q = q.filter(CommunicationTemplate.channel == channel)
        if category:
            q = q.filter(CommunicationTemplate.category == category)
        if status_filter:
            q = q.filter(CommunicationTemplate.status == status_filter)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(CommunicationTemplate.name.ilike(s), CommunicationTemplate.body.ilike(s)))
        q = q.order_by(CommunicationTemplate.name.asc()).offset(skip).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    async def _get(self, actor: User, template_id: uuid.UUID) -> CommunicationTemplate:
        t = (await self.db.execute(select(CommunicationTemplate).filter(
            CommunicationTemplate.id == template_id, CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        return t

    async def get(self, actor: User, template_id: uuid.UUID) -> CommunicationTemplate:
        return await self._get(actor, template_id)

    async def create(self, actor: User, data: dict) -> CommunicationTemplate:
        channel = data.get("channel", "Email")
        if channel not in CHANNELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid channel. Allowed: {list(CHANNELS)}")
        t = CommunicationTemplate(
            organization_id=actor.organization_id, name=data["name"], channel=channel,
            subject=data.get("subject"), body=data["body"], category=data.get("category"),
            description=data.get("description"), created_by=actor.id,
            status="draft", version=1, is_active=data.get("is_active", True))
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def _snapshot(self, actor: User, t: CommunicationTemplate, change_note: str | None) -> None:
        self.db.add(CommunicationTemplateVersion(
            organization_id=t.organization_id, template_id=t.id, version=t.version,
            name=t.name, channel=t.channel, subject=t.subject, body=t.body,
            category=t.category, change_note=change_note, edited_by=actor.id))

    async def update(self, actor: User, template_id: uuid.UUID, data: dict) -> CommunicationTemplate:
        t = await self._get(actor, template_id)
        # snapshot the outgoing version before mutating
        await self._snapshot(actor, t, data.get("change_note"))
        for k in ("name", "subject", "body", "category", "description", "channel", "is_active"):
            if k in data and data[k] is not None:
                if k == "channel" and data[k] not in CHANNELS:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel.")
                setattr(t, k, data[k])
        t.version += 1
        # a content edit sends an approved/rejected template back for re-approval
        if t.status in ("approved", "rejected"):
            t.status = "draft"
            t.approved_by = None
            t.approved_at = None
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def delete(self, actor: User, template_id: uuid.UUID) -> None:
        t = await self._get(actor, template_id)
        if t.created_by != actor.id and not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creator or a Manager/OrgAdmin can delete this template.")
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    # ---------- Approval workflow ----------
    async def submit(self, actor: User, template_id: uuid.UUID) -> CommunicationTemplate:
        t = await self._get(actor, template_id)
        if t.status not in ("draft", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot submit a template in '{t.status}' status.")
        t.status = "pending_approval"
        t.submitted_at = _now()
        t.rejected_reason = None
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def approve(self, actor: User, template_id: uuid.UUID) -> CommunicationTemplate:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Manager or OrgAdmin can approve templates.")
        t = await self._get(actor, template_id)
        if t.status != "pending_approval":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only templates pending approval can be approved.")
        t.status = "approved"
        t.approved_by = actor.id
        t.approved_at = _now()
        t.rejected_reason = None
        self.db.add(t)
        await self.db.flush()
        await self.audit.log_event(organization_id=t.organization_id, actor_user_id=actor.id,
                                   action="TEMPLATE_APPROVED", resource_type="template", resource_id=str(t.id),
                                   action_metadata={"name": t.name})
        await self.db.refresh(t)
        return t

    async def reject(self, actor: User, template_id: uuid.UUID, reason: str | None) -> CommunicationTemplate:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Manager or OrgAdmin can reject templates.")
        t = await self._get(actor, template_id)
        if t.status != "pending_approval":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only templates pending approval can be rejected.")
        t.status = "rejected"
        t.rejected_reason = (reason or "")[:500]
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    # ---------- Version history ----------
    async def versions(self, actor: User, template_id: uuid.UUID) -> list[CommunicationTemplateVersion]:
        await self._get(actor, template_id)  # scope check
        res = await self.db.execute(select(CommunicationTemplateVersion).filter(
            CommunicationTemplateVersion.template_id == template_id,
            CommunicationTemplateVersion.organization_id == actor.organization_id)
            .order_by(CommunicationTemplateVersion.version.desc()))
        return list(res.scalars().all())

    async def restore(self, actor: User, template_id: uuid.UUID, version: int) -> CommunicationTemplate:
        t = await self._get(actor, template_id)
        v = (await self.db.execute(select(CommunicationTemplateVersion).filter(
            CommunicationTemplateVersion.template_id == template_id,
            CommunicationTemplateVersion.organization_id == actor.organization_id,
            CommunicationTemplateVersion.version == version))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        await self._snapshot(actor, t, f"Restored to v{version}")
        t.name, t.subject, t.body, t.category, t.channel = v.name, v.subject, v.body, v.category, v.channel
        t.version += 1
        if t.status in ("approved", "rejected"):
            t.status = "draft"
            t.approved_by = None
            t.approved_at = None
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    # ---------- Usage ----------
    @staticmethod
    async def mark_used(db: AsyncSession, template_id: uuid.UUID) -> None:
        """Increment usage counters — called from the send paths that use a template."""
        t = (await db.execute(select(CommunicationTemplate).filter(
            CommunicationTemplate.id == template_id))).scalars().first()
        if t:
            t.usage_count = (t.usage_count or 0) + 1
            t.last_used_at = _now()
            db.add(t)
            await db.flush()

    # ---------- Test send ----------
    async def test_send(self, actor: User, template_id: uuid.UUID, data: dict) -> dict:
        t = await self._get(actor, template_id)
        rendered = await self.preview(actor, template_id, data)
        subject, body = rendered["subject"], rendered["body"]
        to = (data.get("to") or "").strip()
        await self.mark_used(self.db, t.id)

        if t.channel == "Call":
            # Call scripts are read by the agent, not transmitted.
            return {"sent": False, "channel": "Call", "preview": body}
        if not to:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A test recipient ('to') is required for this channel.")
        if t.channel == "Email":
            from app.services.email_service_module import EmailModuleService
            act = await EmailModuleService(self.db).send(actor, {"subject": subject or t.name, "body": body, "to": to})
            return {"sent": True, "channel": "Email", "activity_id": str(act.id)}
        if t.channel == "SMS":
            from app.services.sms_service import SmsService
            act = await SmsService(self.db).send(actor, {"body": body, "to_number": to}, _skip_cap=True)
            return {"sent": True, "channel": "SMS", "activity_id": str(act.id)}
        if t.channel == "WhatsApp":
            from app.services.whatsapp_service import WhatsAppService
            act = await WhatsAppService(self.db).send_template(actor, {"template_name": t.name, "to_number": to, "body": body})
            return {"sent": True, "channel": "WhatsApp", "activity_id": str(act.id)}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported channel.")

    # ---------- Metadata / reports ----------
    def variables(self) -> list[dict]:
        return VARIABLES

    async def categories(self, actor: User) -> list[str]:
        res = await self.db.execute(select(CommunicationTemplate.category).filter(
            CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.is_deleted == False, CommunicationTemplate.category.isnot(None)).distinct())
        return sorted({c for c in res.scalars().all() if c})

    async def reports(self, actor: User) -> dict:
        q = select(CommunicationTemplate).filter(
            CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.is_deleted == False)
        rows = list((await self.db.execute(q)).scalars().all())
        by_channel: dict = {}
        by_status: dict = {}
        by_category: dict = {}
        total_usage = 0
        for r in rows:
            by_channel[r.channel] = by_channel.get(r.channel, 0) + 1
            by_status[r.status] = by_status.get(r.status, 0) + 1
            cat = r.category or "Uncategorized"
            by_category[cat] = by_category.get(cat, 0) + 1
            total_usage += r.usage_count or 0
        top = sorted(rows, key=lambda r: r.usage_count or 0, reverse=True)[:5]
        return {
            "total": len(rows),
            "total_usage": total_usage,
            "pending_approval": by_status.get("pending_approval", 0),
            "approved": by_status.get("approved", 0),
            "drafts": by_status.get("draft", 0),
            "by_channel": [{"label": k, "count": v} for k, v in sorted(by_channel.items(), key=lambda kv: -kv[1])],
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
            "by_category": [{"label": k, "count": v} for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])],
            "most_used": [{"id": str(r.id), "name": r.name, "channel": r.channel, "usage_count": r.usage_count or 0}
                          for r in top if (r.usage_count or 0) > 0],
        }

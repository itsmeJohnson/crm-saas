"""WhatsApp Business module service.

WhatsApp messages are Activity rows (activity_type='WhatsApp') so they flow
through the Communication Center feed and customer timeline unchanged. On top of
that this service owns the WhatsApp-specific model: per-counterparty
conversations with the 24-hour customer-care window, agent assignment, delivery
+ read receipts, media/template sends, auto-reply, quick replies, and reporting.
Provider config lives in WhatsAppSettings (one row per org).
"""
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.communication import CommunicationFlag, CommunicationTemplate
from app.models.whatsapp import WhatsAppSettings, WhatsAppConversation, WhatsAppQuickReply
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.whatsapp_providers import get_provider

WINDOW_HOURS = 24
MEDIA_TYPES = {"image", "video", "document", "audio"}
DELIVERED_STATUSES = {"delivered", "read"}
FAILED_STATUSES = {"failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WhatsAppService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------- Settings ----------
    async def get_settings(self, actor: User, create: bool = True) -> WhatsAppSettings | None:
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == actor.organization_id, WhatsAppSettings.is_deleted == False))
        s = res.scalars().first()
        if not s and create:
            s = WhatsAppSettings(organization_id=actor.organization_id, provider="mock",
                                 webhook_token=secrets.token_urlsafe(24),
                                 webhook_verify_token=secrets.token_urlsafe(16))
            self.db.add(s)
            await self.db.flush()
            await self.db.refresh(s)
        return s

    async def update_settings(self, actor: User, data: dict) -> WhatsAppSettings:
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can change WhatsApp settings.")
        s = await self.get_settings(actor, create=True)
        for k in ("provider", "phone_number_id", "business_account_id", "access_token", "sender_number",
                  "daily_limit", "auto_reply_enabled", "auto_reply_message", "is_active"):
            if k in data and data[k] is not None:
                setattr(s, k, data[k])
        if data.get("regenerate_webhook_token") or not s.webhook_token:
            s.webhook_token = secrets.token_urlsafe(24)
        if data.get("regenerate_verify_token") or not s.webhook_verify_token:
            s.webhook_verify_token = secrets.token_urlsafe(16)
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return s

    # ---------- Conversations ----------
    async def _get_or_create_conversation(self, org_id: uuid.UUID, phone: str, *, contact_id=None,
                                          lead_id=None, display_name=None) -> WhatsAppConversation:
        phone = (phone or "").strip()
        res = await self.db.execute(select(WhatsAppConversation).filter(
            WhatsAppConversation.organization_id == org_id, WhatsAppConversation.phone == phone,
            WhatsAppConversation.is_deleted == False))
        conv = res.scalars().first()
        if not conv:
            conv = WhatsAppConversation(organization_id=org_id, phone=phone, contact_id=contact_id,
                                        lead_id=lead_id, display_name=display_name)
            self.db.add(conv)
            await self.db.flush()
        else:
            if contact_id and not conv.contact_id:
                conv.contact_id = contact_id
            if lead_id and not conv.lead_id:
                conv.lead_id = lead_id
            if display_name and not conv.display_name:
                conv.display_name = display_name
        return conv

    def _window_open(self, conv: WhatsAppConversation) -> bool:
        if not conv.window_expires_at:
            return False
        exp = conv.window_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > _now()

    async def _resolve_target(self, actor: User, data: dict) -> tuple[str, dict, str | None]:
        """Return (phone, {contact_id, lead_id}, display_name) from an explicit
        conversation_id, phone, or a linked lead/contact."""
        if data.get("conversation_id"):
            conv = await self._get_conversation(actor, data["conversation_id"])
            return conv.phone, {"contact_id": conv.contact_id, "lead_id": conv.lead_id}, conv.display_name
        phone = (data.get("to_number") or data.get("phone") or "").strip()
        contact_id = data.get("contact_id")
        lead_id = data.get("lead_id")
        name = None
        if not phone and lead_id:
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == lead_id, Lead.organization_id == actor.organization_id))).scalars().first()
            if lead:
                phone = (lead.phone or "").strip()
                name = lead.title
        if not phone and contact_id:
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == contact_id, Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                phone = (c.phone or "").strip()
                name = f"{c.first_name or ''} {c.last_name or ''}".strip()
        if not phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No destination: provide a conversation, number, or a lead/contact with a phone.")
        return phone, {"contact_id": contact_id, "lead_id": lead_id}, name

    async def _daily_sent_count(self, org_id: uuid.UUID) -> int:
        start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        res = await self.db.execute(select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id, Activity.activity_type == "WhatsApp",
            Activity.call_direction == "OUTBOUND", Activity.created_at >= start))
        return res.scalar() or 0

    # ---------- Sending ----------
    async def _record_outbound(self, actor: User, conv: WhatsAppConversation, *, body, media_type="text",
                               template_name=None, attachments=None, result, settings_row) -> Activity:
        act = Activity(
            organization_id=actor.organization_id, activity_type="WhatsApp",
            subject=(f"WhatsApp to {conv.phone}" if media_type == "text" else f"WhatsApp {media_type} to {conv.phone}"),
            description=body, status="Completed" if result.status != "failed" else "Failed",
            call_direction="OUTBOUND", assigned_user_id=actor.id, created_by=actor.id,
            contact_id=conv.contact_id, lead_id=conv.lead_id,
            to_number=conv.phone, from_number=(settings_row.sender_number if settings_row else None),
            wa_status=result.status, wa_message_id=result.message_id, wa_error=result.error,
            wa_media_type=media_type, wa_template_name=template_name, wa_conversation_id=conv.id,
            attachments=attachments,
        )
        self.db.add(act)
        await self.db.flush()
        self.db.add(CommunicationFlag(organization_id=actor.organization_id, user_id=actor.id,
                                      activity_id=act.id, is_read=True, read_at=_now()))
        conv.last_outbound_at = _now()
        conv.last_message_at = _now()
        self.db.add(conv)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="WHATSAPP_SENT", resource_type="communication", resource_id=str(act.id),
                                   action_metadata={"to": conv.phone, "type": media_type, "status": result.status,
                                                    "template": template_name})
        return act

    async def _check_cap(self, actor: User, settings_row):
        if settings_row and await self._daily_sent_count(actor.organization_id) >= settings_row.daily_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Daily WhatsApp limit reached ({settings_row.daily_limit}).")

    async def send_text(self, actor: User, data: dict) -> Activity:
        body = (data.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is required.")
        settings_row = await self.get_settings(actor, create=True)
        await self._check_cap(actor, settings_row)
        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"], display_name=name)
        # 24-hour customer-care window: free-form messages require an open window.
        if not self._window_open(conv):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The 24-hour customer window is closed. Send an approved template message to re-open the conversation.")
        provider = get_provider(settings_row)
        result = await provider.send_text(to_number=phone, body=body)
        return await self._record_outbound(actor, conv, body=body, media_type="text", result=result, settings_row=settings_row)

    async def send_template(self, actor: User, data: dict) -> Activity:
        settings_row = await self.get_settings(actor, create=True)
        await self._check_cap(actor, settings_row)
        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"], display_name=name)
        template_name = data.get("template_name")
        body = data.get("body") or ""
        if data.get("template_id"):
            t = (await self.db.execute(select(CommunicationTemplate).filter(
                CommunicationTemplate.id == data["template_id"],
                CommunicationTemplate.organization_id == actor.organization_id,
                CommunicationTemplate.is_deleted == False))).scalars().first()
            if not t:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
            template_name = template_name or t.name
            body = body or t.body
        if not template_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="template_id or template_name is required.")
        provider = get_provider(settings_row)
        result = await provider.send_template(to_number=phone, template_name=template_name, body=body)
        # A template send is allowed to open a fresh 24h window on the business side;
        # the window itself only truly re-opens when the customer replies.
        return await self._record_outbound(actor, conv, body=body, media_type="text",
                                           template_name=template_name, result=result, settings_row=settings_row)

    async def send_media(self, actor: User, data: dict) -> Activity:
        media_url = (data.get("media_url") or "").strip()
        media_type = (data.get("media_type") or "").strip().lower()
        if not media_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="media_url is required.")
        if media_type not in MEDIA_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"media_type must be one of {sorted(MEDIA_TYPES)}.")
        settings_row = await self.get_settings(actor, create=True)
        await self._check_cap(actor, settings_row)
        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"], display_name=name)
        if not self._window_open(conv):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The 24-hour customer window is closed. Send an approved template message first.")
        caption = data.get("caption") or ""
        provider = get_provider(settings_row)
        result = await provider.send_media(to_number=phone, media_url=media_url, media_type=media_type, caption=caption)
        attachments = [{"filename": data.get("filename") or media_url.split("/")[-1], "url": media_url,
                        "media_type": media_type, "uploaded_by": str(actor.id), "uploaded_at": _now().isoformat()}]
        return await self._record_outbound(actor, conv, body=caption, media_type=media_type,
                                           attachments=attachments, result=result, settings_row=settings_row)

    # ---------- Webhooks (token-secured; no auth actor) ----------
    async def _org_by_token(self, token: str) -> WhatsAppSettings:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook token.")
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.webhook_token == token, WhatsAppSettings.is_deleted == False))
        s = res.scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token.")
        return s

    async def verify_webhook(self, verify_token: str, challenge: str) -> str:
        """Meta GET verification handshake: echo the challenge when the verify token matches."""
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.webhook_verify_token == verify_token, WhatsAppSettings.is_deleted == False))
        if not res.scalars().first():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed.")
        return challenge

    async def handle_status(self, token: str, message_id: str, new_status: str) -> dict:
        s = await self._org_by_token(token)
        if not message_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing message id.")
        res = await self.db.execute(select(Activity).filter(
            Activity.organization_id == s.organization_id, Activity.activity_type == "WhatsApp",
            Activity.wa_message_id == message_id))
        act = res.scalars().first()
        if not act:
            return {"status": "ignored", "reason": "unknown message id"}
        # Never regress the receipt ladder sent < delivered < read.
        ladder = {"sent": 1, "delivered": 2, "read": 3}
        if new_status in ladder and ladder.get(act.wa_status or "", 0) > ladder[new_status]:
            return {"status": "stale", "activity_id": str(act.id)}
        act.wa_status = new_status
        if new_status in FAILED_STATUSES:
            act.status = "Failed"
        self.db.add(act)
        await self.db.flush()
        return {"status": "updated", "activity_id": str(act.id), "wa_status": new_status}

    async def _fallback_creator(self, org_id: uuid.UUID, preferred: uuid.UUID | None) -> uuid.UUID:
        """created_by is NOT NULL, but an inbound from an unknown number has no owner.
        Attribute it to the assigned agent when known, else the org's first OrgAdmin,
        else any active user."""
        if preferred:
            return preferred
        admin = (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.role == "OrgAdmin", User.is_active == True,
            User.is_deleted == False).limit(1))).scalar()
        if admin:
            return admin
        return (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.is_active == True, User.is_deleted == False).limit(1))).scalar()

    async def handle_inbound(self, token: str, from_number: str, body: str, message_id: str | None,
                             media_type: str | None = None, media_url: str | None = None) -> dict:
        s = await self._org_by_token(token)
        org_id = s.organization_id
        caller = (from_number or "").strip()
        last10 = caller[-10:] if len(caller) >= 10 else caller

        lead = None
        contact = None
        if last10:
            lead = (await self.db.execute(select(Lead).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False,
                Lead.phone.like(f"%{last10}%")))).scalars().first()
            if not lead:
                contact = (await self.db.execute(select(Contact).filter(
                    Contact.organization_id == org_id, Contact.is_deleted == False,
                    Contact.phone.like(f"%{last10}%")))).scalars().first()

        name = None
        if lead:
            name = lead.title
        elif contact:
            name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()

        conv = await self._get_or_create_conversation(org_id, caller, contact_id=contact.id if contact else None,
                                                      lead_id=lead.id if lead else None, display_name=name)
        # Auto-assign a new/unassigned conversation to the matched entity's owner.
        owner = None
        if lead:
            owner = lead.assigned_user_id or lead.created_by
        elif contact:
            owner = contact.assigned_user_id or contact.created_by
        first_inbound = conv.last_inbound_at is None
        if owner and not conv.assigned_user_id:
            conv.assigned_user_id = owner
        conv.last_inbound_at = _now()
        conv.last_message_at = _now()
        conv.window_expires_at = _now() + timedelta(hours=WINDOW_HOURS)
        conv.unread_count = (conv.unread_count or 0) + 1
        conv.status = "open"
        self.db.add(conv)

        attachments = None
        if media_type and media_url:
            attachments = [{"filename": media_url.split("/")[-1], "url": media_url, "media_type": media_type}]

        creator = await self._fallback_creator(org_id, conv.assigned_user_id)
        act = Activity(
            organization_id=org_id, activity_type="WhatsApp",
            subject=f"WhatsApp from {caller}", description=body or "", status="Completed",
            call_direction="INBOUND", wa_status="received", wa_message_id=message_id,
            wa_media_type=media_type or "text", wa_conversation_id=conv.id,
            assigned_user_id=conv.assigned_user_id, created_by=creator,
            lead_id=lead.id if lead else None, contact_id=contact.id if contact else None,
            to_number=(s.sender_number or ""), from_number=caller, attachments=attachments,
        )
        self.db.add(act)
        await self.db.flush()

        target = conv.assigned_user_id
        if target:
            await self.notifier.create_notification(
                organization_id=org_id, user_id=target, category="whatsapp",
                title="New WhatsApp message",
                body=f"WhatsApp from {name or caller}: {(body or media_type or '')[:80]}",
                link_url=f"/whatsapp?conversationId={conv.id}",
                action_metadata={"conversation_id": str(conv.id), "activity_id": str(act.id), "from": caller})

        # Auto-reply on the first message of a conversation (business greeting).
        auto_reply_sent = False
        if s.auto_reply_enabled and s.auto_reply_message and first_inbound:
            provider = get_provider(s)
            result = await provider.send_text(to_number=caller, body=s.auto_reply_message)
            auto_act = Activity(
                organization_id=org_id, activity_type="WhatsApp", subject=f"WhatsApp to {caller}",
                description=s.auto_reply_message, status="Completed" if result.status != "failed" else "Failed",
                call_direction="OUTBOUND", wa_status=result.status, wa_message_id=result.message_id,
                wa_error=result.error, wa_media_type="text", wa_conversation_id=conv.id,
                assigned_user_id=target, created_by=creator, to_number=caller,
                from_number=(s.sender_number or ""))
            self.db.add(auto_act)
            conv.last_outbound_at = _now()
            self.db.add(conv)
            await self.db.flush()
            auto_reply_sent = True

        # Fire whatsapp_received workflow rules against a matched lead
        if lead and target:
            wf_owner = await self.db.get(User, target)
            if wf_owner:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(self.db).run("whatsapp_received", lead, wf_owner)

        return {"status": "received", "conversation_id": str(conv.id), "activity_id": str(act.id),
                "lead_id": str(lead.id) if lead else None, "contact_id": str(contact.id) if contact else None,
                "auto_reply_sent": auto_reply_sent}

    # ---------- Conversation queries ----------
    def _scope_conv(self, q, actor: User):
        if not self._privileged(actor):
            q = q.filter(WhatsAppConversation.assigned_user_id == actor.id)
        return q

    async def _get_conversation(self, actor: User, conversation_id: uuid.UUID) -> WhatsAppConversation:
        q = select(WhatsAppConversation).filter(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.organization_id == actor.organization_id,
            WhatsAppConversation.is_deleted == False)
        conv = (await self.db.execute(self._scope_conv(q, actor))).scalars().first()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return conv

    async def list_conversations(self, actor: User, status_filter=None, assigned_to=None, search=None,
                                 unread_only=False, skip=0, limit=50) -> list[dict]:
        q = select(WhatsAppConversation).filter(
            WhatsAppConversation.organization_id == actor.organization_id,
            WhatsAppConversation.is_deleted == False)
        q = self._scope_conv(q, actor)
        if status_filter:
            q = q.filter(WhatsAppConversation.status == status_filter)
        if assigned_to:
            q = q.filter(WhatsAppConversation.assigned_user_id == assigned_to)
        if unread_only:
            q = q.filter(WhatsAppConversation.unread_count > 0)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(WhatsAppConversation.phone.ilike(s), WhatsAppConversation.display_name.ilike(s)))
        q = q.order_by(WhatsAppConversation.last_message_at.desc().nullslast()).offset(skip).limit(limit)
        convs = list((await self.db.execute(q)).scalars().all())
        names = await self._names({c.assigned_user_id for c in convs})
        return [self._conv_item(c, names) for c in convs]

    def _conv_item(self, c: WhatsAppConversation, names: dict) -> dict:
        return {
            "id": str(c.id), "phone": c.phone, "display_name": c.display_name,
            "status": c.status, "unread_count": c.unread_count or 0,
            "assigned_user_id": str(c.assigned_user_id) if c.assigned_user_id else None,
            "assigned_user_name": names.get(c.assigned_user_id),
            "window_open": self._window_open(c), "window_expires_at": c.window_expires_at,
            "last_message_at": c.last_message_at, "last_inbound_at": c.last_inbound_at,
            "lead_id": str(c.lead_id) if c.lead_id else None,
            "contact_id": str(c.contact_id) if c.contact_id else None,
        }

    async def thread(self, actor: User, conversation_id: uuid.UUID, mark_read=True) -> dict:
        conv = await self._get_conversation(actor, conversation_id)
        res = await self.db.execute(select(Activity).filter(
            Activity.wa_conversation_id == conv.id, Activity.is_deleted == False).order_by(Activity.created_at.asc()))
        acts = list(res.scalars().all())
        if mark_read and conv.unread_count:
            conv.unread_count = 0
            self.db.add(conv)
            await self.db.flush()
        names = await self._names({conv.assigned_user_id})
        return {"conversation": self._conv_item(conv, names),
                "messages": [self._msg_item(a) for a in acts]}

    def _msg_item(self, a: Activity) -> dict:
        return {
            "id": str(a.id), "direction": a.call_direction, "body": a.description,
            "wa_status": a.wa_status, "media_type": a.wa_media_type, "template_name": a.wa_template_name,
            "error": a.wa_error, "attachments": a.attachments, "timestamp": a.created_at,
            "from_number": a.from_number, "to_number": a.to_number,
        }

    async def assign(self, actor: User, conversation_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Manager or OrgAdmin can assign conversations.")
        q = select(WhatsAppConversation).filter(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.organization_id == actor.organization_id,
            WhatsAppConversation.is_deleted == False)
        conv = (await self.db.execute(q)).scalars().first()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        if user_id:
            u = (await self.db.execute(select(User).filter(
                User.id == user_id, User.organization_id == actor.organization_id, User.is_active == True))).scalars().first()
            if not u:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee not found.")
        conv.assigned_user_id = user_id
        self.db.add(conv)
        await self.db.flush()
        names = await self._names({conv.assigned_user_id})
        return self._conv_item(conv, names)

    # ---------- Quick replies ----------
    async def list_quick_replies(self, actor: User) -> list[WhatsAppQuickReply]:
        res = await self.db.execute(select(WhatsAppQuickReply).filter(
            WhatsAppQuickReply.organization_id == actor.organization_id,
            WhatsAppQuickReply.is_deleted == False).order_by(WhatsAppQuickReply.shortcut.asc()))
        return list(res.scalars().all())

    async def create_quick_reply(self, actor: User, data: dict) -> WhatsAppQuickReply:
        qr = WhatsAppQuickReply(organization_id=actor.organization_id, shortcut=data["shortcut"],
                                text=data["text"], created_by=actor.id)
        self.db.add(qr)
        await self.db.flush()
        await self.db.refresh(qr)
        return qr

    async def delete_quick_reply(self, actor: User, qr_id: uuid.UUID) -> None:
        qr = (await self.db.execute(select(WhatsAppQuickReply).filter(
            WhatsAppQuickReply.id == qr_id, WhatsAppQuickReply.organization_id == actor.organization_id,
            WhatsAppQuickReply.is_deleted == False))).scalars().first()
        if not qr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")
        qr.is_deleted = True
        self.db.add(qr)
        await self.db.flush()

    # ---------- Reports ----------
    async def reports(self, actor: User, date_from=None, date_to=None) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "WhatsApp")
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        acts = list((await self.db.execute(q)).scalars().all())

        by_status: dict = {}
        by_direction: dict = {}
        by_media: dict = {}
        by_day: dict = {}
        outbound = delivered = read = failed = 0
        for a in acts:
            st = a.wa_status or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
            d = a.call_direction or "OUTBOUND"
            by_direction[d] = by_direction.get(d, 0) + 1
            mt = a.wa_media_type or "text"
            by_media[mt] = by_media.get(mt, 0) + 1
            by_day[a.created_at.date().isoformat()] = by_day.get(a.created_at.date().isoformat(), 0) + 1
            if d == "OUTBOUND":
                outbound += 1
                if st in DELIVERED_STATUSES:
                    delivered += 1
                if st == "read":
                    read += 1
                if st in FAILED_STATUSES:
                    failed += 1
        return {
            "total": len(acts),
            "outbound": outbound,
            "inbound": by_direction.get("INBOUND", 0),
            "delivered": delivered,
            "read": read,
            "failed": failed,
            "delivery_rate": round(delivered * 100 / outbound, 1) if outbound else 0.0,
            "read_rate": round(read * 100 / outbound, 1) if outbound else 0.0,
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
            "by_media_type": [{"label": k, "count": v} for k, v in sorted(by_media.items(), key=lambda kv: -kv[1])],
            "by_day": [{"label": day, "count": c} for day, c in sorted(by_day.items())],
        }

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

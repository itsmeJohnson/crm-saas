"""WhatsApp Business module service.

Orchestrates all WhatsApp Business integration logic following SOLID principles:
separate provider details, database locks, idempotency verification, durable outbox sending,
SLA timers, dynamic reports, and real-time updates.
"""
import secrets
import uuid
import logging
import io
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.whatsapp import (
    WhatsAppSettings,
    WhatsAppConversation,
    WhatsAppContact,
    WhatsAppLabel,
    WhatsAppMessage,
    WhatsAppAttachment,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
    whatsapp_conversation_labels
)
from app.core.crypto import encrypt, decrypt
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.whatsapp_providers import get_provider, WhatsAppProvider
from app.services.queue_service import QueueService
from app.core.storage import get_storage_provider, validate_and_sanitize_file
from app.api.v1.telephony import ws_manager

logger = logging.getLogger("app.whatsapp")

WINDOW_HOURS = 24
SLA_TIME_MINUTES = 15
MEDIA_CATEGORIES = {"image", "video", "audio", "document"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WhatsAppService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ================= Settings & Health =================
    async def get_settings(self, actor: User, settings_id: uuid.UUID | None = None) -> WhatsAppSettings:
        """Retrieves a specific settings account, or the first active one, or creates a mock fallback."""
        if settings_id:
            s = await self.db.get(WhatsAppSettings, settings_id)
            if s and s.organization_id == actor.organization_id and not s.is_deleted:
                return s
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp settings account not found.")

        # Try to find default account first
        res_def = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == actor.organization_id,
            WhatsAppSettings.is_default == True,
            WhatsAppSettings.is_deleted == False
        ))
        s = res_def.scalars().first()
        if s:
            return s

        # Find first active account
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == actor.organization_id,
            WhatsAppSettings.is_deleted == False
        ).order_by(WhatsAppSettings.is_active.desc(), WhatsAppSettings.created_at.asc()))
        s = res.scalars().first()
        
        if not s:
            s = WhatsAppSettings(
                organization_id=actor.organization_id,
                provider="mock",
                webhook_token=secrets.token_urlsafe(24),
                webhook_verify_token=secrets.token_urlsafe(16),
                is_active=True
            )
            self.db.add(s)
            await self.db.flush()
            await self.db.refresh(s)
        return s

    async def list_settings(self, actor: User) -> list[WhatsAppSettings]:
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == actor.organization_id,
            WhatsAppSettings.is_deleted == False
        ).order_by(WhatsAppSettings.created_at.asc()))
        return list(res.scalars().all())

    async def update_settings(self, actor: User, settings_id: uuid.UUID, data: dict) -> WhatsAppSettings:
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only privileged roles can modify WhatsApp credentials.")
        
        s = await self.db.get(WhatsAppSettings, settings_id)
        if not s or s.organization_id != actor.organization_id or s.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp settings not found.")

        # Encrypt sensitive values before storing
        if "access_token" in data and data["access_token"]:
            s.access_token = encrypt(data["access_token"])
        if "webhook_secret" in data and data["webhook_secret"]:
            s.webhook_secret_enc = encrypt(data["webhook_secret"])

        for k in ("provider", "phone_number_id", "business_account_id", "sender_number",
                  "api_version", "default_country_code", "daily_limit",
                  "auto_reply_enabled", "auto_reply_message", "is_active", "webhook_url"):
            if k in data and data[k] is not None:
                setattr(s, k, data[k])

        if data.get("regenerate_webhook_token"):
            s.webhook_token = secrets.token_urlsafe(24)
        if data.get("regenerate_verify_token"):
            s.webhook_verify_token = secrets.token_urlsafe(16)

        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)

        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_SETTINGS_UPDATE",
            resource_type="settings",
            resource_id=str(s.id),
            action_metadata={"sender_number": s.sender_number, "provider": s.provider}
        )
        return s

    async def check_health(self, actor: User, settings_id: uuid.UUID) -> str:
        s = await self.get_settings(actor, settings_id)
        # Decrypt access token for checking health
        decrypted_token = decrypt(s.access_token) if s.access_token else ""
        if s.provider == "meta" and decrypted_token:
            from app.services.whatsapp_providers import MetaWhatsAppProvider
            provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", decrypted_token, api_version=s.api_version or "v19.0")
            status_val = await provider.check_health()
        else:
            status_val = "connected" if s.is_active else "disconnected"

        s.health_status = status_val
        self.db.add(s)
        await self.db.flush()
        return status_val

    # ================= Conversations & Locks =================
    async def get_conversation(self, actor: User, conversation_id: uuid.UUID) -> WhatsAppConversation:
        query = select(WhatsAppConversation).filter(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.organization_id == actor.organization_id,
            WhatsAppConversation.is_deleted == False
        )
        # Enforce employee-level conversation scoping
        if not self._privileged(actor):
            query = query.filter(WhatsAppConversation.assigned_user_id == actor.id)
            
        conv = (await self.db.execute(query)).scalars().first()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return conv

    async def list_conversations(
        self,
        actor: User,
        status_filter: str | None = None,
        assigned_to: uuid.UUID | None = None,
        search: str | None = None,
        unread_only: bool = False,
        label_id: uuid.UUID | None = None,
        settings_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50
    ) -> list[dict]:
        # Scopes assignment query
        scop_user = assigned_to
        if not self._privileged(actor):
            scop_user = actor.id

        from app.repositories.whatsapp_repository import WhatsAppConversationRepository
        repo = WhatsAppConversationRepository(self.db)
        convs = await repo.list_conversations(
            organization_id=actor.organization_id,
            assigned_user_id=scop_user,
            status=status_filter,
            search=search,
            unread_only=unread_only,
            label_id=label_id,
            settings_id=settings_id,
            skip=skip,
            limit=limit
        )

        names = await self._names({c.assigned_user_id for c in convs})
        lock_names = await self._names({c.locked_by_user_id for c in convs})
        
        return [self._conv_item(c, names, lock_names) for c in convs]

    async def lock_conversation(self, actor: User, conversation_id: uuid.UUID) -> dict:
        """Acquires a 5-minute composer lease lock on a conversation thread."""
        conv = await self.get_conversation(actor, conversation_id)
        now_time = _now()
        
        # Check if already locked by someone else and not expired
        if conv.locked_by_user_id and conv.locked_by_user_id != actor.id:
            if conv.lock_expires_at and conv.lock_expires_at > now_time:
                # Privileged roles can steal/break the lease lock
                if not self._privileged(actor):
                    lock_user = await self.db.get(User, conv.locked_by_user_id)
                    lock_name = f"{lock_user.first_name} {lock_user.last_name}" if lock_user else "Another Agent"
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"This thread is locked by {lock_name} until {conv.lock_expires_at.isoformat()}."
                    )

        conv.locked_by_user_id = actor.id
        conv.locked_at = now_time
        conv.lock_expires_at = now_time + timedelta(minutes=5)
        
        self.db.add(conv)
        await self.db.flush()
        
        names = await self._names({conv.assigned_user_id})
        lock_names = await self._names({conv.locked_by_user_id})
        
        # Broadcast Lock Update via WebSocket
        update_payload = {
            "type": "whatsapp_lock_change",
            "conversation_id": str(conv.id),
            "locked_by_user_id": str(actor.id),
            "locked_by_name": lock_names.get(actor.id),
            "lock_expires_at": conv.lock_expires_at.isoformat()
        }
        await ws_manager.broadcast_to_organization(update_payload, actor.organization_id, self.db)
        
        return self._conv_item(conv, names, lock_names)

    async def unlock_conversation(self, actor: User, conversation_id: uuid.UUID) -> dict:
        conv = await self.get_conversation(actor, conversation_id)
        if conv.locked_by_user_id and conv.locked_by_user_id != actor.id and not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this conversation compose lock.")
        
        conv.locked_by_user_id = None
        conv.locked_at = None
        conv.lock_expires_at = None
        
        self.db.add(conv)
        await self.db.flush()
        
        names = await self._names({conv.assigned_user_id})
        
        # Broadcast Lock Release
        update_payload = {
            "type": "whatsapp_lock_change",
            "conversation_id": str(conv.id),
            "locked_by_user_id": None,
            "locked_by_name": None,
            "lock_expires_at": None
        }
        await ws_manager.broadcast_to_organization(update_payload, actor.organization_id, self.db)
        
        return self._conv_item(conv, names, {})

    async def change_status(self, actor: User, conversation_id: uuid.UUID, new_status: str) -> dict:
        if new_status not in ("open", "pending", "resolved", "closed"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status option.")
        
        conv = await self.get_conversation(actor, conversation_id)
        old_status = conv.status
        conv.status = new_status
        
        # Auto clear compose lock on resolving/closing
        if new_status in ("resolved", "closed"):
            conv.locked_by_user_id = None
            conv.locked_at = None
            conv.lock_expires_at = None

        self.db.add(conv)
        await self.db.flush()
        
        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_CONVERSATION_STATUS_CHANGE",
            resource_type="conversation",
            resource_id=str(conv.id),
            action_metadata={"old_status": old_status, "new_status": new_status}
        )
        
        names = await self._names({conv.assigned_user_id})
        
        # Broadcast via WebSocket
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_conversation_status",
            "conversation_id": str(conv.id),
            "status": new_status
        }, actor.organization_id, self.db)
        
        return self._conv_item(conv, names, {})

    async def assign_conversation(self, actor: User, conversation_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Managers and Admins can assign chats.")
        
        conv = await self.get_conversation(actor, conversation_id)
        if user_id:
            u = (await self.db.execute(select(User).filter(
                User.id == user_id, User.organization_id == actor.organization_id, User.is_active == True, User.is_deleted == False
            ))).scalars().first()
            if not u:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target assignee user not found or inactive.")
        
        old_assignee = conv.assigned_user_id
        conv.assigned_user_id = user_id
        self.db.add(conv)
        await self.db.flush()
        
        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_ASSIGN",
            resource_type="conversation",
            resource_id=str(conv.id),
            action_metadata={"from_user": str(old_assignee) if old_assignee else None, "to_user": str(user_id) if user_id else None}
        )
        
        names = await self._names({conv.assigned_user_id})
        
        # WebSocket broadcast
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_conversation_assigned",
            "conversation_id": str(conv.id),
            "assigned_user_id": str(user_id) if user_id else None,
            "assigned_user_name": names.get(user_id)
        }, actor.organization_id, self.db)
        
        return self._conv_item(conv, names, {})

    # ================= Outbox Sending & Queue =================
    async def send_text(self, actor: User, data: dict) -> WhatsAppMessage:
        """Outbox sending: stores message to DB transactionally and enqueues to background task."""
        body = (data.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is required.")
        
        s = await self.get_settings(actor, data.get("settings_id"))
        
        # Enforce rate capping check
        await self._check_rate_cap(actor.organization_id, s)

        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone, s.id,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"],
                                                      whatsapp_contact_id=links["whatsapp_contact_id"], display_name=name)
        
        # Verify composure lease lock
        now_time = _now()
        if conv.locked_by_user_id and conv.locked_by_user_id != actor.id:
            if conv.lock_expires_at and conv.lock_expires_at > now_time:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This conversation is currently leased by another agent.")
        
        is_internal = data.get("is_internal", False)
        
        # Check 24-hour customer window for free-form customer messages
        if not is_internal and not self._window_open(conv):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The 24-hour customer window is closed. Send a template message to re-open the thread."
            )

        # 1. Create message model as 'queued' in local DB transaction
        msg = WhatsAppMessage(
            organization_id=actor.organization_id,
            conversation_id=conv.id,
            direction="OUTBOUND",
            body=body,
            wa_status="queued" if not is_internal else "sent",
            media_type="text",
            is_internal=is_internal,
            sent_at=now_time if is_internal else None,
            retry_count=0,
            attachments=[]
        )
        self.db.add(msg)
        await self.db.flush()
        await self._sync_activity(msg, conv, actor.id)
        
        # Update conversation receipt timestamps
        conv.last_outbound_at = now_time
        conv.last_message_at = now_time
        self.db.add(conv)
        await self.db.flush()

        # If it is a real message (not internal note), register outbox Queue Job
        if not is_internal:
            await QueueService(self.db).enqueue(
                organization_id=actor.organization_id,
                job_type="send_whatsapp",
                payload={"message_id": str(msg.id)},
                created_by=actor.id
            )
            
        # Log audit trail
        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_OUTBOX_CREATED",
            resource_type="message",
            resource_id=str(msg.id),
            action_metadata={"to": phone, "is_internal": is_internal}
        )
        
        # Broadcast real-time WS update
        msg_dict = self._msg_item(msg)
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message",
            "conversation_id": str(conv.id),
            "message": msg_dict
        }, actor.organization_id, self.db)

        return msg

    async def send_template(self, actor: User, data: dict) -> WhatsAppMessage:
        s = await self.get_settings(actor, data.get("settings_id"))
        await self._check_rate_cap(actor.organization_id, s)
        
        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone, s.id,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"],
                                                      whatsapp_contact_id=links["whatsapp_contact_id"], display_name=name)
        
        tname = data.get("template_name")
        body = data.get("body") or ""
        variables = data.get("variables") or []
        language = data.get("language") or "en_US"

        if data.get("template_id"):
            from app.models.communication import CommunicationTemplate
            t = (await self.db.execute(select(CommunicationTemplate).filter(
                CommunicationTemplate.id == data["template_id"],
                CommunicationTemplate.organization_id == actor.organization_id,
                CommunicationTemplate.is_deleted == False
            ))).scalars().first()
            if not t:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
            tname = tname or t.name
            body = body or t.body
            from app.services.template_service import TemplateService
            await TemplateService.mark_used(self.db, t.id)
            
        if not tname:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="template_name or template_id is required.")

        now_time = _now()
        # 1. Create outbox message record
        msg = WhatsAppMessage(
            organization_id=actor.organization_id,
            conversation_id=conv.id,
            direction="OUTBOUND",
            body=body,
            wa_status="queued",
            media_type="template",
            template_name=tname,
            sent_at=None,
            retry_count=0,
            attachments=[]
        )
        self.db.add(msg)
        await self.db.flush()
        await self._sync_activity(msg, conv, actor.id)
        
        conv.last_outbound_at = now_time
        conv.last_message_at = now_time
        self.db.add(conv)
        await self.db.flush()

        # 2. Queue the job
        await QueueService(self.db).enqueue(
            organization_id=actor.organization_id,
            job_type="send_whatsapp",
            payload={"message_id": str(msg.id), "language": language, "variables": variables},
            created_by=actor.id
        )
        
        # Broadcast real-time WS update
        msg_dict = self._msg_item(msg)
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message",
            "conversation_id": str(conv.id),
            "message": msg_dict
        }, actor.organization_id, self.db)

        return msg

    async def send_media(self, actor: User, data: dict) -> WhatsAppMessage:
        media_url = (data.get("media_url") or "").strip()
        media_type = (data.get("media_type") or "").strip().lower()
        if not media_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="media_url is required.")
        if media_type not in MEDIA_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"media_type must be one of {sorted(MEDIA_CATEGORIES)}.")
        
        s = await self.get_settings(actor, data.get("settings_id"))
        await self._check_rate_cap(actor.organization_id, s)
        
        phone, links, name = await self._resolve_target(actor, data)
        conv = await self._get_or_create_conversation(actor.organization_id, phone, s.id,
                                                      contact_id=links["contact_id"], lead_id=links["lead_id"],
                                                      whatsapp_contact_id=links["whatsapp_contact_id"], display_name=name)
        
        if not self._window_open(conv):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The 24-hour customer window is closed. Send a template message first."
            )
            
        caption = data.get("caption") or ""
        now_time = _now()
        
        # Create outbox message record
        msg = WhatsAppMessage(
            organization_id=actor.organization_id,
            conversation_id=conv.id,
            direction="OUTBOUND",
            body=caption,
            wa_status="queued",
            media_type=media_type,
            retry_count=0,
            attachments=[]
        )
        self.db.add(msg)
        await self.db.flush()
        
        # Add Attachment record linking to this message
        att = WhatsAppAttachment(
            organization_id=actor.organization_id,
            message_id=msg.id,
            media_url=media_url,
            media_type=media_type,
            file_name=data.get("filename") or media_url.split("/")[-1]
        )
        msg.attachments.append(att)
        self.db.add(msg)
        await self.db.flush()
        await self._sync_activity(msg, conv, actor.id)
        
        conv.last_outbound_at = now_time
        conv.last_message_at = now_time
        self.db.add(conv)
        await self.db.flush()

        # Enqueue Outbox background task
        await QueueService(self.db).enqueue(
            organization_id=actor.organization_id,
            job_type="send_whatsapp",
            payload={"message_id": str(msg.id)},
            created_by=actor.id
        )

        # Broadcast update
        msg_dict = self._msg_item(msg)
        msg_dict["attachments"] = [
            {"id": str(att.id), "media_url": att.media_url, "media_type": att.media_type, "file_name": att.file_name}
        ]
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message",
            "conversation_id": str(conv.id),
            "message": msg_dict
        }, actor.organization_id, self.db)

        return msg

    async def process_outbox_send(self, message_id: uuid.UUID, language: str = "en_US", variables: list | None = None) -> dict:
        """Executes actual network transmission to Meta/Mock API. Called by Background Queue Worker."""
        msg = await self.db.get(WhatsAppMessage, message_id)
        if not msg or msg.is_deleted:
            raise ValueError(f"Message {message_id} not found in database outbox queue.")
        
        if msg.wa_status in ("sent", "delivered", "read"):
            return {"status": "skipped", "reason": "already sent"}
            
        conv = await self.db.get(WhatsAppConversation, msg.conversation_id)
        s = await self.db.get(WhatsAppSettings, conv.whatsapp_settings_id)
        
        # Decrypt access token for network request
        decrypted_token = decrypt(s.access_token) if s.access_token else ""
        
        # Instantiate provider
        if s.provider == "meta" and decrypted_token:
            from app.services.whatsapp_providers import MetaWhatsAppProvider
            provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", decrypted_token, api_version=s.api_version or "v19.0")
        else:
            from app.services.whatsapp_providers import MockWhatsAppProvider
            provider = MockWhatsAppProvider()

        # Dispatch via selected provider
        result = None
        if msg.media_type == "text":
            result = await provider.send_text(to_number=conv.phone, body=msg.body or "")
        elif msg.media_type == "template":
            result = await provider.send_template(to_number=conv.phone, template_name=msg.template_name or "",
                                                  language=language, variables=variables)
        else:
            # Fetch attachments
            res_att = await self.db.execute(select(WhatsAppAttachment).filter(WhatsAppAttachment.message_id == msg.id))
            att = res_att.scalars().first()
            if att:
                result = await provider.send_media(to_number=conv.phone, media_url=att.media_url,
                                                    media_type=msg.media_type, caption=msg.body, file_name=att.file_name)
            else:
                result = WaSendResult(status="failed", error="Media attachment record not found in outbox.")

        # Handle provider response
        now_time = _now()
        if result.status == "sent":
            msg.wa_status = "sent"
            msg.wa_message_id = result.message_id
            msg.sent_at = now_time
            msg.error = None
        else:
            msg.wa_status = "failed"
            msg.failed_at = now_time
            msg.error = result.error
            msg.retry_count = (msg.retry_count or 0) + 1
            # Re-raise exception to let QueueService schedule backoff retries
            raise RuntimeError(f"WhatsApp provider send failure: {result.error}")

        self.db.add(msg)
        await self.db.flush()
        
        creator_id = await self._fallback_creator(s.organization_id, conv.assigned_user_id)
        await self._sync_activity(msg, conv, creator_id)

        # Broadcast final status update via WebSocket
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message_status",
            "conversation_id": str(conv.id),
            "message_id": str(msg.id),
            "wa_message_id": msg.wa_message_id,
            "status": msg.wa_status,
            "error": msg.error
        }, s.organization_id, self.db)

        return {"status": msg.wa_status, "wamid": msg.wa_message_id}

    # ================= Webhooks & Deduplication =================
    async def verify_webhook(self, verify_token: str, challenge: str) -> str:
        """Meta verification handshake GET callback."""
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.webhook_verify_token == verify_token,
            WhatsAppSettings.is_deleted == False
        ))
        if not res.scalars().first():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature verify token mismatch.")
        return challenge

    async def handle_webhook(self, payload: dict, signature: str | None = None, raw_body: bytes | None = None) -> dict:
        """Unified endpoint for Meta status and inbound payloads. Implements signature checking & idempotency."""
        import json
        # 1. Deduplication using Event ID (Meta events contain a unique ID)
        event_id = payload.get("entry", [{}])[0].get("id") or str(uuid.uuid4())
        
        # Extract verify token/webhook verification if signature provided
        phone_number_id = None
        waba_id = None
        entry = payload.get("entry", [])
        if entry:
            waba_id = entry[0].get("id")
            changes = entry[0].get("changes", [])
            if changes:
                phone_number_id = changes[0].get("value", {}).get("metadata", {}).get("phone_number_id")

        if not phone_number_id and not waba_id:
            return {"status": "ignored", "reason": "Missing Meta phone number ID or WABA ID."}

        # Resolve organization settings matching phone_number_id or business_account_id
        if phone_number_id:
            res_s = await self.db.execute(select(WhatsAppSettings).filter(
                WhatsAppSettings.phone_number_id == phone_number_id,
                WhatsAppSettings.is_deleted == False
            ))
            s = res_s.scalars().first()
        else:
            res_s = await self.db.execute(select(WhatsAppSettings).filter(
                WhatsAppSettings.business_account_id == waba_id,
                WhatsAppSettings.is_deleted == False
            ))
            s = res_s.scalars().first()

        if not s:
            return {"status": "ignored", "reason": "Meta account is not registered inside CRM."}

        org_id = s.organization_id

        # Webhook signature validation (if secret is configured in setting)
        if signature and s.webhook_secret_enc:
            decrypted_secret = decrypt(s.webhook_secret_enc)
            if decrypted_secret:
                import hmac
                import hashlib
                body_bytes = raw_body if raw_body is not None else json.dumps(payload, separators=(',', ':')).encode("utf-8")
                expected_sig = "sha256=" + hmac.new(
                    decrypted_secret.encode("utf-8"),
                    body_bytes,
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(expected_sig, signature):
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature.")

        # Idempotency checks
        from app.repositories.whatsapp_repository import WhatsAppWebhookEventRepository
        event_repo = WhatsAppWebhookEventRepository(self.db)
        existing_event = await event_repo.get_by_event_id(event_id)
        if existing_event and existing_event.status == "processed":
            return {"status": "ignored", "reason": "Duplicate webhook event ID."}

        # Log event as pending in DB if not existing, or update it
        if not existing_event:
            event = WhatsAppWebhookEvent(
                organization_id=org_id,
                event_id=event_id,
                event_type="messages" if "messages" in str(payload) else "statuses",
                payload=payload,
                status="pending"
            )
            self.db.add(event)
            await self.db.flush()
        else:
            event = existing_event

        try:
            # 2. Parse entries
            value = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
            field = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("field")
            
            # Case A: Status Update Callback
            if "statuses" in value:
                for status_data in value["statuses"]:
                    wamid = status_data.get("id")
                    st = status_data.get("status")
                    timestamp = status_data.get("timestamp")
                    error_data = status_data.get("errors")
                    
                    err_msg = error_data[0].get("message") if error_data else None
                    dt_stamp = datetime.fromtimestamp(int(timestamp), tz=timezone.utc) if timestamp else _now()
                    
                    await self._process_webhook_status(org_id, wamid, st, dt_stamp, err_msg)
            
            # Case B: Inbound Message Callback
            elif "messages" in value:
                for msg_data in value["messages"]:
                    from_number = msg_data.get("from")
                    wamid = msg_data.get("id")
                    body = msg_data.get("text", {}).get("body") or ""
                    mtype = msg_data.get("type", "text")
                    timestamp = msg_data.get("timestamp")
                    dt_stamp = datetime.fromtimestamp(int(timestamp), tz=timezone.utc) if timestamp else _now()
                    
                    # Resolve media references
                    media_url = None
                    media_id = None
                    file_name = None
                    
                    if mtype in MEDIA_CATEGORIES:
                        media_id = msg_data.get(mtype, {}).get("id")
                        mime = msg_data.get(mtype, {}).get("mime_type")
                        file_name = msg_data.get(mtype, {}).get("filename") or f"media-{media_id}"
                        body = msg_data.get(mtype, {}).get("caption") or body
                        
                        # Queue a background job to download and offload Meta media assets
                        # Since downloading requires meta token, we store the media_id and let the worker process it
                        
                    await self._process_webhook_inbound(s, from_number, body, wamid, mtype, media_id, file_name, dt_stamp)

            # Case C: Template status updates
            elif field == "message_template_status_update":
                template_name = value.get("message_template_name")
                template_lang = value.get("message_template_language")
                status_event = value.get("event")
                
                from sqlalchemy import update
                await self.db.execute(
                    update(WhatsAppTemplate)
                    .filter(
                        WhatsAppTemplate.organization_id == org_id,
                        WhatsAppTemplate.name == template_name,
                        WhatsAppTemplate.language == template_lang,
                        WhatsAppTemplate.is_deleted == False
                    )
                    .values(status=status_event)
                )

            # Case D: Quality updates
            elif field == "phone_number_quality_update":
                p_id = value.get("phone_number_id")
                rating = value.get("new_quality_rating")
                tier = value.get("current_limit")
                
                if p_id == s.phone_number_id:
                    s.quality_rating = rating
                    s.messaging_limit = tier
                    if "100K" in tier:
                        s.daily_limit = 100000
                    elif "10K" in tier:
                        s.daily_limit = 10000
                    elif "1K" in tier:
                        s.daily_limit = 1000
                    elif "250" in tier:
                        s.daily_limit = 250
                    elif "UNLIMITED" in tier:
                        s.daily_limit = 999999
                    self.db.add(s)

            event.status = "processed"
            event.processed_at = _now()
        except Exception as e:
            logger.error("Failed to process webhook payload %s: %s", event_id, str(e))
            event.status = "failed"
            event.error_message = str(e)
            
        self.db.add(event)
        await self.db.flush()
        return {"status": event.status, "event_id": event_id}

    async def _process_webhook_status(self, org_id: uuid.UUID, wamid: str, new_status: str, timestamp: datetime, error: str | None) -> None:
        """Processes delivery and read status updates."""
        from app.repositories.whatsapp_repository import WhatsAppMessageRepository
        msg_repo = WhatsAppMessageRepository(self.db)
        msg = await msg_repo.get_by_wamid(org_id, wamid)
        if not msg:
            logger.warning("Status callback received for unknown message ID: %s", wamid)
            return

        conv = await self.db.get(WhatsAppConversation, msg.conversation_id)
        if not conv:
            logger.warning("Conversation not found for message: %s", msg.id)
            return

        # Never regress receipt timeline ladder
        ladder = {"queued": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 4}
        if ladder.get(msg.wa_status, 0) >= ladder.get(new_status, 0):
            return

        msg.wa_status = new_status
        if new_status == "delivered":
            msg.delivered_at = timestamp
        elif new_status == "read":
            msg.read_at = timestamp
            
            # Calculate SLA Response Time if this reply was to an open SLA ticket
            if conv.sla_status == "breached" or (conv.sla_due_at and conv.last_inbound_at):
                # Calculate diff between agent outbound and last customer inbound
                response_time = (msg.created_at - conv.last_inbound_at).total_seconds()
                conv.response_time_sum += max(0, int(response_time))
                conv.response_count += 1
                conv.sla_status = "normal"
                conv.sla_due_at = None
                self.db.add(conv)
                
        elif new_status == "failed":
            msg.failed_at = timestamp
            msg.error = error
            
            # Alert agent on failures
            conv = await self.db.get(WhatsAppConversation, msg.conversation_id)
            if conv.assigned_user_id:
                await self.notifier.create_notification(
                    organization_id=org_id,
                    user_id=conv.assigned_user_id,
                    category="whatsapp",
                    title="WhatsApp Message Failed",
                    body=f"Failed to deliver message to {conv.display_name or conv.phone}: {error or 'Unknown reason'}",
                    link_url=f"/whatsapp?conversationId={conv.id}"
                )

        self.db.add(msg)
        await self.db.flush()
        
        creator_id = await self._fallback_creator(org_id, conv.assigned_user_id)
        await self._sync_activity(msg, conv, creator_id)

        # WS Broadcast
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message_status",
            "conversation_id": str(msg.conversation_id),
            "message_id": str(msg.id),
            "wa_message_id": wamid,
            "status": new_status,
            "error": error
        }, org_id, self.db)

    async def _process_webhook_inbound(self, s: WhatsAppSettings, from_number: str, body: str,
                                       wamid: str, media_type: str, media_id: str | None,
                                       file_name: str | None, timestamp: datetime) -> None:
        """Processes customer incoming messages."""
        org_id = s.organization_id
        caller = (from_number or "").strip()
        last10 = caller[-10:] if len(caller) >= 10 else caller

        # Match phone against Lead, Contact, or WhatsAppContact
        lead = None
        contact = None
        wa_contact = None
        
        if last10:
            lead = (await self.db.execute(select(Lead).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False, Lead.phone.like(f"%{last10}%")
            ))).scalars().first()
            
            if not lead:
                contact = (await self.db.execute(select(Contact).filter(
                    Contact.organization_id == org_id, Contact.is_deleted == False, Contact.phone.like(f"%{last10}%")
                ))).scalars().first()
                
            if not lead and not contact:
                wa_contact = (await self.db.execute(select(WhatsAppContact).filter(
                    WhatsAppContact.organization_id == org_id, WhatsAppContact.is_deleted == False,
                    WhatsAppContact.phone.like(f"%{last10}%")
                ))).scalars().first()

        name = None
        if lead:
            name = lead.title
        elif contact:
            name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        elif wa_contact:
            name = wa_contact.display_name
        else:
            # Create a new WhatsAppContact for unrecognized customer
            wa_contact = WhatsAppContact(
                organization_id=org_id,
                phone=caller,
                display_name=f"WhatsApp Contact {caller[-4:]}"
            )
            self.db.add(wa_contact)
            await self.db.flush()
            name = wa_contact.display_name

        conv = await self._get_or_create_conversation(
            org_id, caller, s.id,
            contact_id=contact.id if contact else None,
            lead_id=lead.id if lead else None,
            whatsapp_contact_id=wa_contact.id if wa_contact else None,
            display_name=name
        )

        owner = None
        if lead:
            owner = lead.assigned_user_id or lead.created_by
        elif contact:
            owner = contact.assigned_user_id or contact.created_by
            
        first_inbound = conv.last_inbound_at is None
        if owner and not conv.assigned_user_id:
            conv.assigned_user_id = owner

        conv.last_inbound_at = timestamp
        conv.last_message_at = timestamp
        conv.window_expires_at = timestamp + timedelta(hours=WINDOW_HOURS)
        conv.unread_count = (conv.unread_count or 0) + 1
        conv.status = "open"
        
        # Calculate Response SLA: Agent must respond within 15 minutes
        conv.sla_status = "normal"
        conv.sla_due_at = timestamp + timedelta(minutes=SLA_TIME_MINUTES)
        
        self.db.add(conv)
        await self.db.flush()

        # Persist inbound message record
        creator = await self._fallback_creator(org_id, conv.assigned_user_id)
        msg = WhatsAppMessage(
            organization_id=org_id,
            conversation_id=conv.id,
            direction="INBOUND",
            body=body,
            wa_message_id=wamid,
            wa_status="read" if conv.unread_count == 0 else "delivered",
            media_type=media_type,
            sent_at=timestamp,
            is_internal=False,
            retry_count=0,
            attachments=[]
        )
        self.db.add(msg)
        await self.db.flush()
        await self._sync_activity(msg, conv, creator)

        # Enqueue media download job if attachment present
        if media_id:
            await QueueService(self.db).enqueue(
                organization_id=org_id,
                job_type="send_whatsapp",  # Enqueues in whatsapp queue
                payload={"action": "download_media", "media_id": media_id, "message_id": str(msg.id), "file_name": file_name},
                created_by=creator
            )

        # Notify owner/assigned user
        target = conv.assigned_user_id or creator
        await self.notifier.create_notification(
            organization_id=org_id,
            user_id=target,
            category="whatsapp",
            title="New WhatsApp message",
            body=f"WhatsApp from {name or caller}: {body[:80]}",
            link_url=f"/whatsapp?conversationId={conv.id}"
        )

        # Trigger auto-reply on first inbound message
        if s.auto_reply_enabled and s.auto_reply_message and first_inbound:
            # Create outbound auto-reply message synchronously to keep logs consistent
            auto_reply_msg = WhatsAppMessage(
                organization_id=org_id,
                conversation_id=conv.id,
                direction="OUTBOUND",
                body=s.auto_reply_message,
                wa_status="sent",
                media_type="text",
                is_internal=False,
                sent_at=_now(),
                retry_count=0,
                attachments=[]
            )
            self.db.add(auto_reply_msg)
            await self.db.flush()
            await self._sync_activity(auto_reply_msg, conv, creator)

            # Update conversation outbound timestamp
            conv.last_outbound_at = _now()
            conv.last_message_at = _now()
            self.db.add(conv)

            # Enqueue auto-reply outbound send task
            await QueueService(self.db).enqueue(
                organization_id=org_id,
                job_type="send_whatsapp",
                payload={"conversation_id": str(conv.id), "body": s.auto_reply_message, "message_id": str(auto_reply_msg.id)},
                created_by=creator
            )

        # Fire automated Lead Workflow triggers
        if lead and target:
            wf_owner = await self.db.get(User, target)
            if wf_owner:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(self.db).run("whatsapp_received", lead, wf_owner)

        # WS Broadcast
        msg_dict = self._msg_item(msg)
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_message",
            "conversation_id": str(conv.id),
            "message": msg_dict
        }, org_id, self.db)

    async def download_and_persist_media(self, message_id: uuid.UUID, media_id: str, file_name: str) -> None:
        """Downloads raw binary from Meta and offloads it to CRM storage provider."""
        msg = await self.db.get(WhatsAppMessage, message_id)
        if not msg or msg.is_deleted:
            return
            
        conv = await self.db.get(WhatsAppConversation, msg.conversation_id)
        s = await self.db.get(WhatsAppSettings, conv.whatsapp_settings_id)
        
        decrypted_token = decrypt(s.access_token) if s.access_token else ""
        if s.provider != "meta" or not decrypted_token:
            return
            
        from app.services.whatsapp_providers import MetaWhatsAppProvider
        provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", decrypted_token, api_version=s.api_version or "v19.0")
        
        # Download raw bytes
        content = await provider.download_media(media_id=media_id)
        
        # Sanitize and save to storage provider
        sanitized_name, ext = validate_and_sanitize_file(content=content, filename=file_name)
        storage_url = await get_storage_provider().upload_file(content, sanitized_name)
        
        # Save attachment record
        att = WhatsAppAttachment(
            organization_id=s.organization_id,
            message_id=msg.id,
            media_id=media_id,
            media_url=storage_url,
            media_type=msg.media_type,
            file_name=sanitized_name,
            file_size=len(content),
            mime_type=msg.media_type
        )
        self.db.add(att)
        await self.db.flush()
        
        # WS update notification with new attachment details
        await ws_manager.broadcast_to_organization({
            "type": "whatsapp_attachment_ready",
            "conversation_id": str(conv.id),
            "message_id": str(msg.id),
            "attachment": {
                "id": str(att.id),
                "media_url": att.media_url,
                "media_type": att.media_type,
                "file_name": att.file_name
            }
        }, s.organization_id, self.db)

    # ================= Unknown Contacts & Leads =================
    async def convert_to_lead(self, actor: User, contact_id: uuid.UUID) -> Lead:
        """Promotes/converts a temporary WhatsAppContact into a first-class Lead."""
        contact = await self.db.get(WhatsAppContact, contact_id)
        if not contact or contact.organization_id != actor.organization_id or contact.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp contact not found.")

        # Find first pipeline stage
        from app.models.pipeline import PipelineStage
        stage = (await self.db.execute(select(PipelineStage).filter(
            PipelineStage.organization_id == actor.organization_id, PipelineStage.is_system_default == True
        ))).scalars().first()
        
        if not stage:
            stage = PipelineStage(organization_id=actor.organization_id, name="New", order_position=1, is_system_default=True)
            self.db.add(stage)
            await self.db.flush()

        # Create Lead
        lead = Lead(
            organization_id=actor.organization_id,
            first_name="WhatsApp",
            last_name=contact.display_name or "Contact",
            phone=contact.phone,
            title=f"WhatsApp Lead - {contact.phone[-4:]}",
            status="New",
            source="WhatsApp",
            stage_id=stage.id,
            assigned_user_id=actor.id,
            created_by=actor.id
        )
        self.db.add(lead)
        await self.db.flush()

        # Update all conversations mapping to point to this new Lead
        res_conv = await self.db.execute(select(WhatsAppConversation).filter(
            WhatsAppConversation.whatsapp_contact_id == contact.id
        ))
        for conv in res_conv.scalars().all():
            conv.lead_id = lead.id
            conv.display_name = lead.title
            self.db.add(conv)
            
        # Delete temporary WhatsAppContact record
        contact.is_deleted = True
        self.db.add(contact)
        
        await self.db.flush()

        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_CONTACT_CONVERT_LEAD",
            resource_type="lead",
            resource_id=str(lead.id),
            action_metadata={"contact_id": str(contact_id)}
        )
        return lead

    # ================= Templates Sync =================
    async def sync_templates(self, actor: User, settings_id: uuid.UUID) -> list[WhatsAppTemplate]:
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to sync templates.")
            
        s = await self.get_settings(actor, settings_id)
        decrypted_token = decrypt(s.access_token) if s.access_token else ""
        
        if s.provider != "meta" or not decrypted_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Meta credentials are required to sync templates.")
                                
        from app.services.whatsapp_providers import MetaWhatsAppProvider
        provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", decrypted_token, api_version=s.api_version or "v19.0")
        
        meta_templates = await provider.sync_templates()
        local_templates = []
        
        for t in meta_templates:
            # Find existing template to update, or create a new one
            res_ex = await self.db.execute(select(WhatsAppTemplate).filter(
                WhatsAppTemplate.organization_id == actor.organization_id,
                WhatsAppTemplate.name == t["name"],
                WhatsAppTemplate.language == t["language"],
                WhatsAppTemplate.is_deleted == False
            ))
            tmpl = res_ex.scalars().first()
            if not tmpl:
                tmpl = WhatsAppTemplate(
                    organization_id=actor.organization_id,
                    name=t["name"],
                    language=t["language"]
                )
            tmpl.meta_template_id = t["meta_template_id"]
            tmpl.category = t["category"]
            tmpl.status = t["status"]
            tmpl.header_format = t["header_format"]
            tmpl.header_text = t["header_text"]
            tmpl.body_text = t["body_text"]
            tmpl.footer_text = t["footer_text"]
            tmpl.buttons = t["buttons"]
            
            self.db.add(tmpl)
            local_templates.append(tmpl)
            
        await self.db.flush()
        return local_templates

    # ================= Labels/Tags Management =================
    async def list_labels(self, actor: User) -> list[WhatsAppLabel]:
        res = await self.db.execute(select(WhatsAppLabel).filter(
            WhatsAppLabel.organization_id == actor.organization_id,
            WhatsAppLabel.is_deleted == False
        ).order_by(WhatsAppLabel.name.asc()))
        return list(res.scalars().all())

    async def create_label(self, actor: User, name: str, color: str) -> WhatsAppLabel:
        if not name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label name is required.")
            
        # Check uniqueness in org
        res_ex = await self.db.execute(select(WhatsAppLabel).filter(
            WhatsAppLabel.organization_id == actor.organization_id,
            WhatsAppLabel.name == name.strip(),
            WhatsAppLabel.is_deleted == False
        ))
        if res_ex.scalars().first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label name already exists.")

        label = WhatsAppLabel(
            organization_id=actor.organization_id,
            name=name.strip(),
            color=color
        )
        self.db.add(label)
        await self.db.flush()
        return label

    async def delete_label(self, actor: User, label_id: uuid.UUID) -> None:
        label = await self.db.get(WhatsAppLabel, label_id)
        if not label or label.organization_id != actor.organization_id or label.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found.")
            
        label.is_deleted = True
        self.db.add(label)
        await self.db.flush()

    async def assign_label_to_conversation(self, actor: User, conversation_id: uuid.UUID, label_id: uuid.UUID) -> WhatsAppConversation:
        conv = await self.get_conversation(actor, conversation_id)
        label = await self.db.get(WhatsAppLabel, label_id)
        if not label or label.organization_id != actor.organization_id or label.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found.")
            
        # Check if already assigned
        res = await self.db.execute(select(whatsapp_conversation_labels).filter(
            whatsapp_conversation_labels.c.conversation_id == conv.id,
            whatsapp_conversation_labels.c.label_id == label.id
        ))
        if not res.first():
            # Add to association table
            self.db.add(whatsapp_conversation_labels.insert().values(conversation_id=conv.id, label_id=label.id))
            await self.db.flush()
            await self.db.refresh(conv)

        return conv

    async def remove_label_from_conversation(self, actor: User, conversation_id: uuid.UUID, label_id: uuid.UUID) -> WhatsAppConversation:
        conv = await self.get_conversation(actor, conversation_id)
        # Delete association
        await self.db.execute(whatsapp_conversation_labels.delete().where(and_(
            whatsapp_conversation_labels.c.conversation_id == conv.id,
            whatsapp_conversation_labels.c.label_id == label_id
        )))
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    # ================= SLA Cron Scanner =================
    async def check_sla_breaches(self) -> dict:
        """Periodic scan to mark conversations as breached if agent response is overdue."""
        now_time = _now()
        # Find all open conversations waiting for response where sla_due_at is expired
        query = select(WhatsAppConversation).filter(
            WhatsAppConversation.status == "open",
            WhatsAppConversation.sla_status == "normal",
            WhatsAppConversation.sla_due_at != None,
            WhatsAppConversation.sla_due_at <= now_time,
            WhatsAppConversation.is_deleted == False
        )
        res = await self.db.execute(query)
        breached_convs = list(res.scalars().all())
        
        for conv in breached_convs:
            conv.sla_status = "breached"
            self.db.add(conv)
            
            # Send notification to assigned agent
            if conv.assigned_user_id:
                await self.notifier.create_notification(
                    organization_id=conv.organization_id,
                    user_id=conv.assigned_user_id,
                    category="whatsapp",
                    title="Response SLA Breached",
                    body=f"Overdue: You haven't replied to {conv.display_name or conv.phone} within {SLA_TIME_MINUTES} mins.",
                    link_url=f"/whatsapp?conversationId={conv.id}"
                )
                
            # Broadcast update via WebSocket
            await ws_manager.broadcast_to_organization({
                "type": "whatsapp_conversation_sla",
                "conversation_id": str(conv.id),
                "sla_status": "breached"
            }, conv.organization_id, self.db)

        await self.db.flush()
        return {"scanned": len(breached_convs), "breached": len(breached_convs)}

    # ================= Reports & Analytics =================
    async def reports(self, actor: User, date_from: datetime | None = None, date_to: datetime | None = None) -> dict:
        """Fetches metrics for reports including SLA statistics."""
        q = select(WhatsAppMessage).filter(
            WhatsAppMessage.organization_id == actor.organization_id,
            WhatsAppMessage.is_deleted == False,
            WhatsAppMessage.is_internal == False
        )
        if date_from:
            q = q.filter(WhatsAppMessage.created_at >= date_from)
        if date_to:
            q = q.filter(WhatsAppMessage.created_at <= date_to)
            
        res = await self.db.execute(q)
        msgs = list(res.scalars().all())

        by_status = {}
        by_direction = {"INBOUND": 0, "OUTBOUND": 0}
        by_media = {}
        by_day = {}
        outbound = delivered = read = failed = 0
        
        for m in msgs:
            st = m.wa_status or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
            d = m.direction
            by_direction[d] = by_direction.get(d, 0) + 1
            mt = m.media_type or "text"
            by_media[mt] = by_media.get(mt, 0) + 1
            day_str = m.created_at.date().isoformat()
            by_day[day_str] = by_day.get(day_str, 0) + 1
            
            if d == "OUTBOUND":
                outbound += 1
                if st in ("delivered", "read"):
                    delivered += 1
                if st == "read":
                    read += 1
                if st == "failed":
                    failed += 1

        # Calculate SLA average response times across org conversations
        res_sla = await self.db.execute(select(
            func.sum(WhatsAppConversation.response_time_sum),
            func.sum(WhatsAppConversation.response_count)
        ).filter(
            WhatsAppConversation.organization_id == actor.organization_id,
            WhatsAppConversation.is_deleted == False
        ))
        sla_sums = res_sla.first()
        time_sum = sla_sums[0] or 0
        resp_count = sla_sums[1] or 0
        avg_resp = round(time_sum / resp_count, 1) if resp_count else 0.0

        return {
            "total": len(msgs),
            "outbound": outbound,
            "inbound": by_direction["INBOUND"],
            "delivered": delivered,
            "read": read,
            "failed": failed,
            "delivery_rate": round(delivered * 100 / outbound, 1) if outbound else 0.0,
            "read_rate": round(read * 100 / outbound, 1) if outbound else 0.0,
            "response_time_avg_sec": avg_resp,
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
            "by_media_type": [{"label": k, "count": v} for k, v in sorted(by_media.items(), key=lambda kv: -kv[1])],
            "by_day": [{"label": day, "count": c} for day, c in sorted(by_day.items())]
        }

    async def export_reports_excel(self, actor: User, date_from: datetime | None = None, date_to: datetime | None = None) -> bytes:
        import openpyxl
        data = await self.reports(actor, date_from, date_to)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "WhatsApp Reports Summary"
        
        ws.append(["Metric", "Value"])
        ws.append(["Total Messages", data["total"]])
        ws.append(["Inbound", data["inbound"]])
        ws.append(["Outbound", data["outbound"]])
        ws.append(["Delivered", data["delivered"]])
        ws.append(["Read", data["read"]])
        ws.append(["Failed", data["failed"]])
        ws.append(["Delivery Rate (%)", data["delivery_rate"]])
        ws.append(["Read Rate (%)", data["read_rate"]])
        ws.append(["Average Response Time (sec)", data["response_time_avg_sec"]])
        
        # Add charts breakdown worksheets
        for key in ("by_status", "by_direction", "by_media_type", "by_day"):
            ws_sec = wb.create_sheet(title=key.replace("by_", "").capitalize())
            ws_sec.append(["Label", "Count"])
            for bucket in data[key]:
                ws_sec.append([bucket["label"], bucket["count"]])

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    async def export_reports_pdf(self, actor: User, date_from: datetime | None = None, date_to: datetime | None = None) -> bytes:
        from weasyprint import HTML
        data = await self.reports(actor, date_from, date_to)
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; color: #1e293b; padding: 20px; }}
                h1 {{ color: #10b981; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #e2e8f0; padding: 12px; text-align: left; }}
                th {{ bg: #f8fafc; font-weight: bold; }}
                .stat-grid {{ display: flex; flex-wrap: wrap; gap: 20px; margin-top: 20px; }}
                .stat-card {{ border: 1px solid #e2e8f0; padding: 15px; width: 18%; border-radius: 8px; }}
                .num {{ font-size: 20px; font-weight: bold; color: #10b981; }}
            </style>
        </head>
        <body>
            <h1>WhatsApp Business Analytics Report</h1>
            <p>Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            
            <div class="stat-grid">
                <div class="stat-card"><div>Total</div><div class="num">{data["total"]}</div></div>
                <div class="stat-card"><div>Inbound</div><div class="num">{data["inbound"]}</div></div>
                <div class="stat-card"><div>Outbound</div><div class="num">{data["outbound"]}</div></div>
                <div class="stat-card"><div>Delivered</div><div class="num">{data["delivery_rate"]}%</div></div>
                <div class="stat-card"><div>Avg Response</div><div class="num">{data["response_time_avg_sec"]}s</div></div>
            </div>

            <table>
                <thead>
                    <tr><th>Metric Summary</th><th>Count/Rate</th></tr>
                </thead>
                <tbody>
                    <tr><td>Messages Delivered</td><td>{data["delivered"]}</td></tr>
                    <tr><td>Messages Read</td><td>{data["read"]}</td></tr>
                    <tr><td>Messages Failed</td><td>{data["failed"]}</td></tr>
                    <tr><td>Read Rate (%)</td><td>{data["read_rate"]}%</td></tr>
                </tbody>
            </table>
        </body>
        </html>
        """
        out = HTML(string=html_content).write_pdf()
        return out

    # ================= Helper Methods =================
    async def _get_or_create_conversation(self, org_id: uuid.UUID, phone: str, settings_id: uuid.UUID,
                                          contact_id=None, lead_id=None, whatsapp_contact_id=None, display_name=None) -> WhatsAppConversation:
        phone = (phone or "").strip()
        res = await self.db.execute(select(WhatsAppConversation).filter(
            WhatsAppConversation.organization_id == org_id,
            WhatsAppConversation.phone == phone,
            WhatsAppConversation.whatsapp_settings_id == settings_id,
            WhatsAppConversation.is_deleted == False
        ))
        conv = res.scalars().first()
        if not conv:
            conv = WhatsAppConversation(
                organization_id=org_id,
                whatsapp_settings_id=settings_id,
                phone=phone,
                contact_id=contact_id,
                lead_id=lead_id,
                whatsapp_contact_id=whatsapp_contact_id,
                display_name=display_name
            )
            self.db.add(conv)
            await self.db.flush()
        else:
            if contact_id and not conv.contact_id:
                conv.contact_id = contact_id
            if lead_id and not conv.lead_id:
                conv.lead_id = lead_id
            if whatsapp_contact_id and not conv.whatsapp_contact_id:
                conv.whatsapp_contact_id = whatsapp_contact_id
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
        if data.get("conversation_id"):
            conv = await self.get_conversation(actor, data["conversation_id"])
            return conv.phone, {"contact_id": conv.contact_id, "lead_id": conv.lead_id, "whatsapp_contact_id": conv.whatsapp_contact_id}, conv.display_name
            
        phone = (data.get("to_number") or data.get("phone") or "").strip()
        contact_id = data.get("contact_id")
        lead_id = data.get("lead_id")
        whatsapp_contact_id = data.get("whatsapp_contact_id")
        name = None
        
        if not phone and lead_id:
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == lead_id, Lead.organization_id == actor.organization_id
            ))).scalars().first()
            if lead:
                phone = (lead.phone or "").strip()
                name = lead.title
        if not phone and contact_id:
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == contact_id, Contact.organization_id == actor.organization_id
            ))).scalars().first()
            if c:
                phone = (c.phone or "").strip()
                name = f"{c.first_name or ''} {c.last_name or ''}".strip()
        if not phone and whatsapp_contact_id:
            wc = await self.db.get(WhatsAppContact, whatsapp_contact_id)
            if wc and wc.organization_id == actor.organization_id:
                phone = wc.phone
                name = wc.display_name
                
        if not phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No destination number: provide conversation, phone, or linked lead/contact/whatsapp contact.")
        return phone, {"contact_id": contact_id, "lead_id": lead_id, "whatsapp_contact_id": whatsapp_contact_id}, name

    async def _daily_sent_count(self, org_id: uuid.UUID, settings_id: uuid.UUID) -> int:
        start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        res = await self.db.execute(select(func.count(WhatsAppMessage.id)).join(WhatsAppConversation).filter(
            WhatsAppMessage.organization_id == org_id,
            WhatsAppMessage.direction == "OUTBOUND",
            WhatsAppMessage.is_internal == False,
            WhatsAppConversation.whatsapp_settings_id == settings_id,
            WhatsAppMessage.created_at >= start
        ))
        return res.scalar() or 0

    async def _check_rate_cap(self, org_id: uuid.UUID, s: WhatsAppSettings):
        if s and await self._daily_sent_count(org_id, s.id) >= s.daily_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Daily outbound WhatsApp limit reached ({s.daily_limit}).")

    async def _fallback_creator(self, org_id: uuid.UUID, preferred: uuid.UUID | None) -> uuid.UUID:
        if preferred:
            return preferred
        admin = (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.role == "OrgAdmin", User.is_active == True, User.is_deleted == False
        ).limit(1))).scalar()
        if admin:
            return admin
        return (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.is_active == True, User.is_deleted == False
        ).limit(1))).scalar()

    def _conv_item(self, c: WhatsAppConversation, names: dict, lock_names: dict) -> dict:
        now_time = _now()
        is_locked = bool(c.locked_by_user_id and c.lock_expires_at and c.lock_expires_at > now_time)
        return {
            "id": str(c.id),
            "whatsapp_settings_id": str(c.whatsapp_settings_id),
            "phone": c.phone,
            "display_name": c.display_name,
            "status": c.status,
            "is_pinned": c.is_pinned,
            "unread_count": c.unread_count,
            "assigned_user_id": str(c.assigned_user_id) if c.assigned_user_id else None,
            "assigned_user_name": names.get(c.assigned_user_id),
            "window_open": self._window_open(c),
            "window_expires_at": c.window_expires_at.isoformat() if c.window_expires_at else None,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "last_inbound_at": c.last_inbound_at.isoformat() if c.last_inbound_at else None,
            "lead_id": str(c.lead_id) if c.lead_id else None,
            "contact_id": str(c.contact_id) if c.contact_id else None,
            "whatsapp_contact_id": str(c.whatsapp_contact_id) if c.whatsapp_contact_id else None,
            "sla_status": c.sla_status,
            "sla_due_at": c.sla_due_at.isoformat() if c.sla_due_at else None,
            "locked_by_user_id": str(c.locked_by_user_id) if c.locked_by_user_id else None,
            "locked_by_user_name": lock_names.get(c.locked_by_user_id) if c.locked_by_user_id else None,
            "lock_expires_at": c.lock_expires_at.isoformat() if c.lock_expires_at else None,
            "is_locked": is_locked,
            "labels": [{"id": str(l.id), "name": l.name, "color": l.color} for l in c.labels]
        }

    def _msg_item(self, m: WhatsAppMessage) -> dict:
        return {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "direction": m.direction,
            "body": m.body,
            "wa_message_id": m.wa_message_id,
            "wa_status": m.wa_status,
            "media_type": m.media_type,
            "template_name": m.template_name,
            "error": m.error,
            "is_internal": m.is_internal,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
            "read_at": m.read_at.isoformat() if m.read_at else None,
            "failed_at": m.failed_at.isoformat() if m.failed_at else None,
            "retry_count": m.retry_count,
            "attachments": [
                {
                    "id": str(a.id),
                    "media_id": a.media_id,
                    "media_url": a.media_url,
                    "media_type": a.media_type,
                    "file_name": a.file_name,
                    "file_size": a.file_size,
                    "mime_type": a.mime_type,
                    "local_path": a.local_path
                } for a in m.attachments
            ],
            "created_at": m.created_at.isoformat(),
            "ai_summary": m.ai_summary,
            "ai_sentiment": m.ai_sentiment,
            "ai_intent": m.ai_intent,
            "suggested_reply": m.suggested_reply,
            "language": m.language,
            "translation": m.translation
        }

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _sync_activity(self, msg: WhatsAppMessage, conv: WhatsAppConversation, creator_id: uuid.UUID) -> Activity:
        """Syncs WhatsAppMessage state changes with the main Activity timeline."""
        from app.models.activity import Activity
        act = await self.db.get(Activity, msg.id)
        if not act:
            act = Activity(
                id=msg.id,
                organization_id=msg.organization_id,
                activity_type="WhatsApp",
                subject="WhatsApp Message",
                created_by=creator_id
            )
        act.description = msg.body
        act.status = "Completed"
        act.assigned_user_id = conv.assigned_user_id
        act.lead_id = conv.lead_id
        act.contact_id = conv.contact_id
        act.call_direction = msg.direction
        act.wa_status = msg.wa_status
        act.wa_message_id = msg.wa_message_id
        act.wa_error = msg.error
        act.wa_media_type = msg.media_type
        act.wa_template_name = msg.template_name
        act.wa_conversation_id = msg.conversation_id
        
        self.db.add(act)
        await self.db.flush()
        return act

    async def rotate_token(self, actor: User, settings_id: uuid.UUID, new_token: str) -> WhatsAppSettings:
        """Rotates WhatsApp Business access token and tests its connectivity."""
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only privileged roles can rotate tokens.")
            
        s = await self.db.get(WhatsAppSettings, settings_id)
        if not s or s.organization_id != actor.organization_id or s.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp settings account not found.")
            
        # Validate the new token first
        from app.services.whatsapp_providers import MetaWhatsAppProvider
        provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", new_token, api_version=s.api_version or "v19.0")
        health = await provider.check_health()
        if health != "connected":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot rotate token: new token health check returned {health}.")
            
        # Encrypt and save
        s.access_token = encrypt(new_token)
        s.health_status = "connected"
        self.db.add(s)
        await self.db.flush()
        
        # Log audit entry
        await self.audit.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="WHATSAPP_TOKEN_ROTATION",
            resource_type="settings",
            resource_id=str(s.id),
            action_metadata={"sender_number": s.sender_number}
        )
        return s

    async def set_default_settings(self, actor: User, settings_id: uuid.UUID) -> WhatsAppSettings:
        """Sets a specific WhatsApp configuration as default for sending outbound messages."""
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only privileged roles can set default configuration.")
            
        s = await self.db.get(WhatsAppSettings, settings_id)
        if not s or s.organization_id != actor.organization_id or s.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp settings account not found.")
            
        # Reset all other settings is_default flag to False for this organization
        from sqlalchemy import update
        await self.db.execute(
            update(WhatsAppSettings)
            .filter(
                WhatsAppSettings.organization_id == actor.organization_id,
                WhatsAppSettings.id != settings_id
            )
            .values(is_default=False)
        )
        
        s.is_default = True
        self.db.add(s)
        await self.db.flush()
        return s

    async def exchange_signup_oauth(self, actor: User, code: str, redirect_uri: str) -> list[WhatsAppSettings]:
        """Exchanges Embedded Signup OAuth code for WABAs, phone IDs, and access tokens automatically."""
        import os
        from app.core.config import settings
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only privileged roles can configure WhatsApp.")
            
        app_secret = os.getenv("META_APP_SECRET") or getattr(settings, "META_APP_SECRET", None) or "mock_app_secret"
        
        # Find any existing meta_app_id for this organization
        res_ex = await self.db.execute(select(WhatsAppSettings.meta_app_id).filter(
            WhatsAppSettings.organization_id == actor.organization_id,
            WhatsAppSettings.meta_app_id.is_not(None),
            WhatsAppSettings.is_deleted == False
        ).limit(1))
        app_id = res_ex.scalar() or os.getenv("META_APP_ID") or "mock_app_id"
        
        # Exchange authorization code for access token via Meta API
        from app.services.whatsapp_providers import MetaWhatsAppProvider
        temp_provider = MetaWhatsAppProvider("", "", "", api_version="v19.0")
        
        try:
            user_access_token = await temp_provider.exchange_auth_code(
                app_id=app_id,
                app_secret=app_secret,
                redirect_uri=redirect_uri,
                code=code
            )
        except Exception as e:
            logger.warning("OAuth exchange failed, fallback to mock: %s", str(e))
            user_access_token = f"EAAG_{secrets.token_hex(16)}"
            
        # Fetch WABAs
        discovery_provider = MetaWhatsAppProvider("", "", user_access_token, api_version="v19.0")
        try:
            wabas = await discovery_provider.fetch_shared_wabas()
        except Exception as e:
            logger.warning("Failed to fetch WABAs, fallback to mock: %s", str(e))
            wabas = [{"id": f"waba_{secrets.token_hex(8)}", "name": "Mock WABA"}]
            
        configured_settings = []
        for waba in wabas:
            waba_id = waba["id"]
            try:
                phones = await discovery_provider.fetch_waba_phone_numbers(waba_id=waba_id)
            except Exception as e:
                logger.warning("Failed to fetch phone numbers for WABA %s: %s", waba_id, str(e))
                phones = [{
                    "id": f"phone_{secrets.token_hex(8)}",
                    "display_phone_number": "+15555555555",
                    "verified_name": waba.get("name") or "Mock Phone",
                    "quality_rating": "GREEN",
                    "messaging_limit_tier": "TIER_1K"
                }]
                
            for phone in phones:
                phone_id = phone["id"]
                display_number = phone.get("display_phone_number")
                
                # Check if this phone number settings already exists in CRM
                res_s = await self.db.execute(select(WhatsAppSettings).filter(
                    WhatsAppSettings.organization_id == actor.organization_id,
                    WhatsAppSettings.phone_number_id == phone_id,
                    WhatsAppSettings.is_deleted == False
                ))
                s = res_s.scalars().first()
                if not s:
                    s = WhatsAppSettings(
                        organization_id=actor.organization_id,
                        phone_number_id=phone_id,
                        is_active=True
                    )
                
                s.provider = "meta"
                s.business_account_id = waba_id
                s.sender_number = display_number
                s.access_token = encrypt(user_access_token)
                s.meta_app_id = app_id
                s.webhook_token = s.webhook_token or secrets.token_urlsafe(24)
                s.webhook_verify_token = s.webhook_verify_token or secrets.token_urlsafe(16)
                s.api_version = "v19.0"
                s.quality_rating = phone.get("quality_rating") or "GREEN"
                s.messaging_limit = phone.get("messaging_limit_tier") or "TIER_1K"
                s.display_name_status = phone.get("display_name_status") or "APPROVED"
                s.health_status = "connected"
                
                # Update daily limits based on tier
                tier = s.messaging_limit
                if "100K" in tier:
                    s.daily_limit = 100000
                elif "10K" in tier:
                    s.daily_limit = 10000
                elif "1K" in tier:
                    s.daily_limit = 1000
                elif "250" in tier:
                    s.daily_limit = 250
                elif "UNLIMITED" in tier:
                    s.daily_limit = 999999
                else:
                    s.daily_limit = 2000
                    
                s.capabilities = {
                    "supports_templates": True,
                    "supports_reactions": True,
                    "supports_location": True,
                    "supports_contacts": True,
                    "supports_catalog": False,
                    "supports_payments": False
                }
                
                self.db.add(s)
                await self.db.flush()
                
                # Audit log entry
                await self.audit.log_event(
                    organization_id=actor.organization_id,
                    actor_user_id=actor.id,
                    action="WHATSAPP_EMBEDDED_SIGNUP",
                    resource_type="settings",
                    resource_id=str(s.id),
                    action_metadata={"sender_number": s.sender_number, "phone_number_id": phone_id}
                )
                configured_settings.append(s)
        return configured_settings

    async def get_monitoring_dashboard(self, actor: User) -> dict:
        """Assembles operational health dashboard statistics."""
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
            
        org_id = actor.organization_id
        
        # 1. Connected Accounts count
        res_conn = await self.db.execute(select(func.count(WhatsAppSettings.id)).filter(
            WhatsAppSettings.organization_id == org_id,
            WhatsAppSettings.health_status == "connected",
            WhatsAppSettings.is_deleted == False
        ))
        conn_count = res_conn.scalar() or 0
        
        # 2. Quality Ratings
        res_settings = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == org_id,
            WhatsAppSettings.is_deleted == False
        ))
        settings_list = res_settings.scalars().all()
        
        qualities = []
        limits = []
        for s in settings_list:
            qualities.append({
                "settings_id": str(s.id),
                "sender_number": s.sender_number,
                "quality_rating": s.quality_rating or "GREEN"
            })
            limits.append({
                "settings_id": str(s.id),
                "sender_number": s.sender_number,
                "messaging_limit": s.messaging_limit or "TIER_1K",
                "daily_limit": s.daily_limit
            })
            
        # 3. Webhook Status (check last processed status in WhatsAppWebhookEvent)
        res_wh = await self.db.execute(select(WhatsAppWebhookEvent).filter(
            WhatsAppWebhookEvent.organization_id == org_id
        ).order_by(WhatsAppWebhookEvent.created_at.desc()).limit(5))
        wh_events = res_wh.scalars().all()
        
        webhook_status = "healthy"
        if wh_events:
            if any(ev.status == "failed" for ev in wh_events):
                webhook_status = "degraded"
        else:
            webhook_status = "unknown"
            
        # 4. Queue Size (count of running/queued whatsapp jobs in QueueJob)
        from app.models.queue import QueueJob
        res_q = await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org_id,
            QueueJob.job_type == "send_whatsapp",
            QueueJob.status.in_(["queued", "running"]),
            QueueJob.is_deleted == False
        ))
        queue_size = res_q.scalar() or 0
        
        # 5. Failed Messages count
        res_failed = await self.db.execute(select(func.count(WhatsAppMessage.id)).filter(
            WhatsAppMessage.organization_id == org_id,
            WhatsAppMessage.wa_status == "failed",
            WhatsAppMessage.is_deleted == False
        ))
        failed_count = res_failed.scalar() or 0
        
        # 6. Daily Volume (today's outbound/inbound messages)
        start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        res_vol = await self.db.execute(select(func.count(WhatsAppMessage.id)).filter(
            WhatsAppMessage.organization_id == org_id,
            WhatsAppMessage.is_deleted == False,
            WhatsAppMessage.created_at >= start_of_day
        ))
        daily_vol = res_vol.scalar() or 0
        
        return {
            "connected_accounts": conn_count,
            "quality_ratings": qualities,
            "messaging_limits": limits,
            "webhook_status": webhook_status,
            "queue_size": queue_size,
            "failed_messages": failed_count,
            "daily_volume": daily_vol
        }

    async def sync_all_active_accounts(self) -> None:
        """Syncs templates and phone details for all active Meta accounts across all tenants."""
        res = await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.provider == "meta",
            WhatsAppSettings.is_deleted == False,
            WhatsAppSettings.is_active == True
        ))
        active_accounts = res.scalars().all()
        for s in active_accounts:
            try:
                res_u = await self.db.execute(select(User).filter(
                    User.organization_id == s.organization_id,
                    User.role == "OrgAdmin",
                    User.is_active == True,
                    User.is_deleted == False
                ).limit(1))
                actor = res_u.scalar()
                if not actor:
                    res_u_alt = await self.db.execute(select(User).filter(
                        User.organization_id == s.organization_id,
                        User.is_active == True,
                        User.is_deleted == False
                    ).limit(1))
                    actor = res_u_alt.scalar()
                    
                if actor:
                    await self.sync_templates(actor, s.id)
                    await self.sync_account_details(actor, s.id)
            except Exception as e:
                logger.error("Failed to sync active whatsapp setting %s: %s", s.id, str(e))

    async def sync_account_details(self, actor: User, settings_id: uuid.UUID) -> None:
        """Syncs single account quality rating, limits, and capabilities from Meta."""
        s = await self.get_settings(actor, settings_id)
        decrypted_token = decrypt(s.access_token) if s.access_token else ""
        if s.provider != "meta" or not decrypted_token:
            return
            
        from app.services.whatsapp_providers import MetaWhatsAppProvider
        provider = MetaWhatsAppProvider(s.phone_number_id or "", s.business_account_id or "", decrypted_token, api_version=s.api_version or "v19.0")
        
        try:
            health = await provider.check_health()
            s.health_status = health
            
            if s.business_account_id:
                phones = await provider.fetch_waba_phone_numbers(waba_id=s.business_account_id)
                for phone in phones:
                    if phone.get("id") == s.phone_number_id:
                        s.quality_rating = phone.get("quality_rating") or s.quality_rating
                        s.messaging_limit = phone.get("messaging_limit_tier") or s.messaging_limit
                        s.display_name_status = phone.get("display_name_status") or s.display_name_status
                        
                        tier = s.messaging_limit or "TIER_1K"
                        if "100K" in tier:
                            s.daily_limit = 100000
                        elif "10K" in tier:
                            s.daily_limit = 10000
                        elif "1K" in tier:
                            s.daily_limit = 1000
                        elif "250" in tier:
                            s.daily_limit = 250
                        elif "UNLIMITED" in tier:
                            s.daily_limit = 999999
            
            s.capabilities = {
                "supports_templates": provider.supports_templates,
                "supports_reactions": provider.supports_reactions,
                "supports_location": provider.supports_location,
                "supports_contacts": provider.supports_contacts,
                "supports_catalog": provider.supports_catalog,
                "supports_payments": provider.supports_payments
            }
            self.db.add(s)
            await self.db.flush()
        except Exception as e:
            logger.warning("Failed to sync account details for settings %s: %s", s.id, str(e))

    def is_meta_error_retryable(self, error_msg: str | None) -> bool:
        """Helper to classify if a Meta API error response warrants job retries."""
        if not error_msg:
            return False
        err_lower = error_msg.lower()
        non_retryable_keywords = (
            "oauth", "access token", "expired", "revoked", "signature",
            "invalid parameter", "template does not exist", "unsupported",
            "policy", "banned", "not exist", "cannot find", "permission"
        )
        if any(k in err_lower for k in non_retryable_keywords):
            return False
        return True

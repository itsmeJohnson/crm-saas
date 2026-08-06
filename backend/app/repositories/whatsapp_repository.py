import uuid
from typing import Sequence, List
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.whatsapp import (
    WhatsAppSettings,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppAttachment,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
    WhatsAppLabel,
    WhatsAppContact
)


class WhatsAppSettingsRepository(BaseRepository[WhatsAppSettings]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppSettings, db)

    async def get_by_org(self, organization_id: uuid.UUID) -> List[WhatsAppSettings]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_phone_number_id(self, organization_id: uuid.UUID, phone_number_id: str) -> WhatsAppSettings | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.phone_number_id == phone_number_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_webhook_token(self, webhook_token: str) -> WhatsAppSettings | None:
        # Global query needed for incoming webhook verification without org_id context
        query = select(self.model).filter(
            self.model.webhook_token == webhook_token,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_verify_token(self, verify_token: str) -> WhatsAppSettings | None:
        # Global query for subscription verification handshake
        query = select(self.model).filter(
            self.model.webhook_verify_token == verify_token,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()


class WhatsAppConversationRepository(BaseRepository[WhatsAppConversation]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppConversation, db)

    async def get_by_phone(self, organization_id: uuid.UUID, phone: str, settings_id: uuid.UUID) -> WhatsAppConversation | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.phone == phone,
            self.model.whatsapp_settings_id == settings_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_id_in_org(self, organization_id: uuid.UUID, conversation_id: uuid.UUID) -> WhatsAppConversation | None:
        query = select(self.model).filter(
            self.model.id == conversation_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_conversations(
        self,
        organization_id: uuid.UUID,
        assigned_user_id: uuid.UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        unread_only: bool = False,
        label_id: uuid.UUID | None = None,
        settings_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50
    ) -> Sequence[WhatsAppConversation]:
        from sqlalchemy.orm import selectinload
        query = select(self.model).options(
            selectinload(self.model.labels),
            selectinload(self.model.whatsapp_contact)
        ).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        if assigned_user_id:
            query = query.filter(self.model.assigned_user_id == assigned_user_id)
        if status:
            query = query.filter(self.model.status == status)
        if settings_id:
            query = query.filter(self.model.whatsapp_settings_id == settings_id)
        if unread_only:
            query = query.filter(self.model.unread_count > 0)
        if label_id:
            # Filters conversation by label join table
            from app.models.whatsapp import whatsapp_conversation_labels
            query = query.join(whatsapp_conversation_labels).filter(
                whatsapp_conversation_labels.c.label_id == label_id
            )
        if search:
            search_str = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.phone.ilike(search_str),
                    self.model.display_name.ilike(search_str)
                )
            )
        query = query.order_by(self.model.is_pinned.desc(), self.model.last_message_at.desc().nullslast()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()


class WhatsAppMessageRepository(BaseRepository[WhatsAppMessage]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppMessage, db)

    async def get_by_wamid(self, organization_id: uuid.UUID, wa_message_id: str) -> WhatsAppMessage | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.wa_message_id == wa_message_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_wamid_global(self, wa_message_id: str) -> WhatsAppMessage | None:
        query = select(self.model).filter(
            self.model.wa_message_id == wa_message_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_thread(self, organization_id: uuid.UUID, conversation_id: uuid.UUID, skip: int = 0, limit: int = 50) -> Sequence[WhatsAppMessage]:
        from sqlalchemy.orm import selectinload
        query = select(self.model).options(
            selectinload(self.model.attachments)
        ).filter(
            self.model.organization_id == organization_id,
            self.model.conversation_id == conversation_id,
            self.model.is_deleted == False
        ).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        # Reverse to return ascending chronological order
        return list(reversed(result.scalars().all()))


class WhatsAppAttachmentRepository(BaseRepository[WhatsAppAttachment]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppAttachment, db)

    async def get_by_message(self, organization_id: uuid.UUID, message_id: uuid.UUID) -> List[WhatsAppAttachment]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.message_id == message_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


class WhatsAppTemplateRepository(BaseRepository[WhatsAppTemplate]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppTemplate, db)

    async def get_by_name_and_lang(self, organization_id: uuid.UUID, name: str, language: str) -> WhatsAppTemplate | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.name == name,
            self.model.language == language,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_templates(self, organization_id: uuid.UUID, search: str | None = None, skip: int = 0, limit: int = 100) -> Sequence[WhatsAppTemplate]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        if search:
            query = query.filter(self.model.name.ilike(f"%{search}%"))
        query = query.order_by(self.model.name.asc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()


class WhatsAppWebhookEventRepository(BaseRepository[WhatsAppWebhookEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppWebhookEvent, db)

    async def get_by_event_id(self, event_id: str) -> WhatsAppWebhookEvent | None:
        query = select(self.model).filter(
            self.model.event_id == event_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_failed(self, organization_id: uuid.UUID, limit: int = 100) -> Sequence[WhatsAppWebhookEvent]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.status == "failed",
            self.model.is_deleted == False
        ).order_by(self.model.created_at.asc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()


class WhatsAppLabelRepository(BaseRepository[WhatsAppLabel]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppLabel, db)

    async def get_by_name(self, organization_id: uuid.UUID, name: str) -> WhatsAppLabel | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.name == name,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_labels(self, organization_id: uuid.UUID) -> Sequence[WhatsAppLabel]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        ).order_by(self.model.name.asc())
        result = await self.db.execute(query)
        return result.scalars().all()


class WhatsAppContactRepository(BaseRepository[WhatsAppContact]):
    def __init__(self, db: AsyncSession):
        super().__init__(WhatsAppContact, db)

    async def get_by_phone(self, organization_id: uuid.UUID, phone: str) -> WhatsAppContact | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.phone == phone,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

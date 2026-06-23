import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.commercial_settings import CommercialSettingsRepository
from app.models.commercial_settings import CommercialSettings
from app.schemas.commercial_settings import CommercialSettingsUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger("commercial_settings_service")

class CommercialSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommercialSettingsRepository(db)
        self.audit_service = AuditService(db)

    async def get_settings(self) -> CommercialSettings:
        return await self.repo.get_default()

    async def update_settings(
        self,
        payload: CommercialSettingsUpdate,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> CommercialSettings:
        settings = await self.repo.get_default()
        
        # Calculate diff for audit log
        old_val = {}
        new_val = {}
        # Exclude reason when dumping settings values
        update_data = payload.model_dump(exclude_unset=True)
        reason = update_data.pop("reason", None)
        
        for field, value in update_data.items():
            if hasattr(settings, field):
                current_value = getattr(settings, field)
                if current_value != value:
                    old_val[field] = str(current_value) if current_value is not None else ""
                    new_val[field] = str(value) if value is not None else ""
                    setattr(settings, field, value)

        settings.updated_at = datetime.now(timezone.utc)
        self.db.add(settings)
        await self.db.flush()

        # Log change events
        if old_val:
            action_metadata = {
                "old": old_val,
                "new": new_val,
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            if reason:
                action_metadata["reason"] = reason

            await self.audit_service.log_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="COMMERCIAL_SETTINGS_UPDATED",
                resource_type="CommercialSettings",
                resource_id="default",
                action_metadata=action_metadata
            )
            
        return settings

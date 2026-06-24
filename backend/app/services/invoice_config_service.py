import os
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.invoice_config import InvoiceConfigRepository
from app.models.invoice_config import InvoiceConfig
from app.schemas.invoice_config import InvoiceConfigUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger("invoice_config_service")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "branding")

class InvoiceConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InvoiceConfigRepository(db)
        self.audit_service = AuditService(db)

    async def get_config(self) -> InvoiceConfig:
        return await self.repo.get_default()

    async def update_config(
        self,
        payload: InvoiceConfigUpdate,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> InvoiceConfig:
        config = await self.repo.get_default()
        
        # Calculate diff for audit log
        old_val = {}
        new_val = {}
        update_data = payload.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            current_value = getattr(config, field)
            if current_value != value:
                old_val[field] = str(current_value) if current_value is not None else ""
                new_val[field] = str(value) if value is not None else ""
                setattr(config, field, value)

        config.updated_at = datetime.now(timezone.utc)
        self.db.add(config)
        await self.db.flush()

        # Log change events
        if old_val:
            await self.audit_service.log_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="INVOICE_CONFIG_UPDATED",
                resource_type="InvoiceConfig",
                resource_id="default",
                action_metadata={
                    "old": old_val,
                    "new": new_val,
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )
            
        return config

    async def upload_logo(
        self,
        file_bytes: bytes,
        original_filename: str,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> str:
        from app.core.storage import validate_and_sanitize_file, get_storage_provider
        
        # Validate file size, extension, and magic bytes signature
        filename, ext = validate_and_sanitize_file(
            content=file_bytes,
            filename=original_filename,
            allowed_extensions={"jpg", "jpeg", "png", "webp", "svg", "pdf"},
            max_size=2 * 1024 * 1024
        )
        
        provider = get_storage_provider()
        
        config = await self.repo.get_default()
        old_logo = config.company_logo_url or ""
        
        # Clean up old file using provider
        if old_logo:
            await provider.delete_file(old_logo)

        # Upload new file
        logo_url = await provider.upload_file(file_bytes, filename)
        
        config.company_logo_url = logo_url
        config.updated_at = datetime.now(timezone.utc)
        self.db.add(config)
        await self.db.flush()

        # Audit log
        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="INVOICE_LOGO_UPDATED",
            resource_type="InvoiceConfig",
            resource_id="default",
            action_metadata={
                "old": {"company_logo_url": old_logo},
                "new": {"company_logo_url": logo_url},
                "ip_address": ip_address,
                "user_agent": user_agent
            }
        )

        return logo_url

    async def upload_qr_code(
        self,
        file_bytes: bytes,
        original_filename: str,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> str:
        from app.core.storage import validate_and_sanitize_file, get_storage_provider
        
        # Validate file size, extension, and magic bytes signature
        filename, ext = validate_and_sanitize_file(
            content=file_bytes,
            filename=original_filename,
            allowed_extensions={"jpg", "jpeg", "png", "webp", "svg", "pdf"},
            max_size=2 * 1024 * 1024
        )
        
        provider = get_storage_provider()

        config = await self.repo.get_default()
        old_qr = config.qr_code_url or ""
        
        # Clean up old file using provider
        if old_qr:
            await provider.delete_file(old_qr)

        # Upload new file
        qr_url = await provider.upload_file(file_bytes, filename)
        
        config.qr_code_url = qr_url
        config.updated_at = datetime.now(timezone.utc)
        self.db.add(config)
        await self.db.flush()

        # Audit log
        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="INVOICE_QR_UPDATED",
            resource_type="InvoiceConfig",
            resource_id="default",
            action_metadata={
                "old": {"qr_code_url": old_qr},
                "new": {"qr_code_url": qr_url},
                "ip_address": ip_address,
                "user_agent": user_agent
            }
        )

        return qr_url

    async def delete_logo(
        self,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> None:
        config = await self.repo.get_default()
        old_logo = config.company_logo_url or ""
        if old_logo:
            from app.core.storage import get_storage_provider
            provider = get_storage_provider()
            await provider.delete_file(old_logo)

            config.company_logo_url = None
            config.updated_at = datetime.now(timezone.utc)
            self.db.add(config)
            await self.db.flush()

            # Audit log
            await self.audit_service.log_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="INVOICE_LOGO_DELETED",
                resource_type="InvoiceConfig",
                resource_id="default",
                action_metadata={
                    "old": {"company_logo_url": old_logo},
                    "new": {"company_logo_url": ""},
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )

    async def delete_qr_code(
        self,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> None:
        config = await self.repo.get_default()
        old_qr = config.qr_code_url or ""
        if old_qr:
            from app.core.storage import get_storage_provider
            provider = get_storage_provider()
            await provider.delete_file(old_qr)

            config.qr_code_url = None
            config.updated_at = datetime.now(timezone.utc)
            self.db.add(config)
            await self.db.flush()

            # Audit log
            await self.audit_service.log_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="INVOICE_QR_DELETED",
                resource_type="InvoiceConfig",
                resource_id="default",
                action_metadata={
                    "old": {"qr_code_url": old_qr},
                    "new": {"qr_code_url": ""},
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )


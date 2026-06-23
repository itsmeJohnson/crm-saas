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
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(original_filename)[1] or ".png"
        filename = f"logo_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(file_bytes)

        config = await self.repo.get_default()
        old_logo = config.company_logo_url or ""
        logo_url = f"/api/v1/uploads/branding/{filename}"
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
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(original_filename)[1] or ".png"
        filename = f"qr_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(file_bytes)

        config = await self.repo.get_default()
        old_qr = config.qr_code_url or ""
        qr_url = f"/api/v1/uploads/branding/{filename}"
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
            # Try to delete file on disk
            try:
                filename = old_logo.split("/")[-1]
                filepath = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.error(f"Error deleting logo file: {e}")

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
            # Try to delete file on disk
            try:
                filename = old_qr.split("/")[-1]
                filepath = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.error(f"Error deleting QR code file: {e}")

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

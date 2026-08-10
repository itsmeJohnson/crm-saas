import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org_invoice_settings import OrgInvoiceSettings
from app.models.user import User


class OrgInvoiceSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, organization_id: uuid.UUID) -> OrgInvoiceSettings:
        row = (await self.db.execute(select(OrgInvoiceSettings).filter(
            OrgInvoiceSettings.organization_id == organization_id,
            OrgInvoiceSettings.is_deleted == False))).scalar_one_or_none()
        if row:
            return row
        row = OrgInvoiceSettings(organization_id=organization_id)
        self.db.add(row)
        await self.db.flush()
        return row

    async def get(self, actor: User) -> OrgInvoiceSettings:
        settings = await self.get_or_create(actor.organization_id)
        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    async def update(self, actor: User, data: dict) -> OrgInvoiceSettings:
        settings = await self.get_or_create(actor.organization_id)
        for k, v in data.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    async def allocate_invoice_number(self, organization_id: uuid.UUID) -> str:
        """Atomically reserve the next invoice number for the tenant. Locks the
        settings row so concurrent invoice creation can't reuse a number."""
        settings = (await self.db.execute(select(OrgInvoiceSettings).filter(
            OrgInvoiceSettings.organization_id == organization_id,
            OrgInvoiceSettings.is_deleted == False).with_for_update())).scalar_one_or_none()
        if not settings:
            settings = OrgInvoiceSettings(organization_id=organization_id)
            self.db.add(settings)
            await self.db.flush()
        n = settings.next_invoice_number or 1
        settings.next_invoice_number = n + 1
        pad = settings.number_padding or 0
        seq = str(n).zfill(pad) if pad else str(n)
        return f"{settings.invoice_prefix or ''}{seq}"

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invoice_config import InvoiceConfig
from app.repositories.base import BaseRepository

class InvoiceConfigRepository(BaseRepository[InvoiceConfig]):
    def __init__(self, db: AsyncSession):
        super().__init__(InvoiceConfig, db)

    async def get_default(self) -> InvoiceConfig:
        config = await self.db.get(InvoiceConfig, "default")
        if not config:
            config = InvoiceConfig(id="default")
            self.db.add(config)
            await self.db.flush()
        return config

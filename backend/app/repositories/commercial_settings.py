from sqlalchemy.ext.asyncio import AsyncSession
from app.models.commercial_settings import CommercialSettings
from app.repositories.base import BaseRepository

class CommercialSettingsRepository(BaseRepository[CommercialSettings]):
    def __init__(self, db: AsyncSession):
        super().__init__(CommercialSettings, db)

    async def get_default(self) -> CommercialSettings:
        config = await self.db.get(CommercialSettings, "default")
        if not config:
            config = CommercialSettings(id="default")
            self.db.add(config)
            await self.db.flush()
        return config

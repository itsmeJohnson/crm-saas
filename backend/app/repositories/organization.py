from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, db: AsyncSession):
        super().__init__(Organization, db)

    async def get_by_slug(self, slug: str) -> Organization | None:
        query = select(self.model).filter(
            self.model.slug == slug,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

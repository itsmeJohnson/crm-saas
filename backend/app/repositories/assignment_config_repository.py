import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.assignment_config import AssignmentConfig
from app.repositories.base import BaseRepository

class AssignmentConfigRepository(BaseRepository[AssignmentConfig]):
    def __init__(self, db: AsyncSession):
        super().__init__(AssignmentConfig, db)

    async def get_by_org(self, organization_id: uuid.UUID) -> AssignmentConfig | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

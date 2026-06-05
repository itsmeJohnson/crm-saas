import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.lead_import import LeadImport
from app.repositories.base import BaseRepository

class LeadImportRepository(BaseRepository[LeadImport]):
    def __init__(self, db: AsyncSession):
        super().__init__(LeadImport, db)

    async def get_import_by_id(self, organization_id: uuid.UUID, import_id: uuid.UUID) -> LeadImport | None:
        query = select(self.model).filter(
            self.model.id == import_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_imports(self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100) -> Sequence[LeadImport]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        ).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

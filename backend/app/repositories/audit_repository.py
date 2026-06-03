import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository

class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def create_log(self, organization_id: uuid.UUID, log_data: dict) -> AuditLog:
        log_data["organization_id"] = organization_id
        return await self.create(log_data)

    async def list_logs(self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100) -> Sequence[AuditLog]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id
        ).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def list_user_logs(self, organization_id: uuid.UUID, actor_user_id: uuid.UUID, skip: int = 0, limit: int = 100) -> Sequence[AuditLog]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.actor_user_id == actor_user_id
        ).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

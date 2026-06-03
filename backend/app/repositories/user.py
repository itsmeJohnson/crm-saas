from typing import Sequence, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        query = select(self.model).filter(
            self.model.email == email,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_organization(self, organization_id: Any, skip: int = 0, limit: int = 100) -> Sequence[User]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        ).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

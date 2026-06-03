from datetime import datetime, timezone
from typing import Any, Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import UserSession
from app.repositories.base import BaseRepository

class UserSessionRepository(BaseRepository[UserSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserSession, db)

    async def get_by_refresh_token(self, refresh_token: str) -> UserSession | None:
        query = select(self.model).filter(
            self.model.refresh_token == refresh_token,
            self.model.is_revoked == False,
            self.model.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def revoke_all_user_sessions(self, user_id: Any) -> None:
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id, self.model.is_revoked == False)
            .values(is_revoked=True)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        
    async def revoke_session(self, session_id: Any) -> None:
        stmt = (
            update(self.model)
            .where(self.model.id == session_id)
            .values(is_revoked=True)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        
    async def get_active_sessions(self, user_id: Any) -> Sequence[UserSession]:
        query = select(self.model).filter(
            self.model.user_id == user_id,
            self.model.is_revoked == False,
            self.model.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

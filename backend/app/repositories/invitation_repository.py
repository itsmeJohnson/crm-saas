import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invitation import UserInvitation
from app.repositories.base import BaseRepository

class InvitationRepository(BaseRepository[UserInvitation]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserInvitation, db)

    async def create_invitation(self, organization_id: uuid.UUID, invite_data: dict) -> UserInvitation:
        invite_data["organization_id"] = organization_id
        return await self.create(invite_data)

    async def get_by_token(self, organization_id: uuid.UUID, token: str) -> UserInvitation | None:
        query = select(self.model).filter(
            self.model.token == token,
            self.model.organization_id == organization_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_pending_invites(self, organization_id: uuid.UUID) -> Sequence[UserInvitation]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.accepted == False,
            self.model.revoked == False,
            self.model.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def mark_accepted(self, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> UserInvitation | None:
        query = select(self.model).filter(
            self.model.id == invitation_id,
            self.model.organization_id == organization_id
        )
        result = await self.db.execute(query)
        invite = result.scalars().first()
        if invite:
            invite.accepted = True
            self.db.add(invite)
            await self.db.flush()
        return invite

    async def revoke_invite(self, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> UserInvitation | None:
        query = select(self.model).filter(
            self.model.id == invitation_id,
            self.model.organization_id == organization_id
        )
        result = await self.db.execute(query)
        invite = result.scalars().first()
        if invite:
            invite.revoked = True
            self.db.add(invite)
            await self.db.flush()
        return invite

    async def existing_pending_invite(self, organization_id: uuid.UUID, email: str) -> UserInvitation | None:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.email == email,
            self.model.accepted == False,
            self.model.revoked == False,
            self.model.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_filter import SavedFilter
from app.models.user import User


class SavedFilterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_filters(self, actor: User, entity_type: str | None = None) -> list[SavedFilter]:
        """Return the actor's own saved filters plus any shared org-wide ones."""
        query = select(SavedFilter).filter(
            SavedFilter.organization_id == actor.organization_id,
            SavedFilter.is_deleted == False,
            or_(SavedFilter.user_id == actor.id, SavedFilter.is_shared == True),
        )
        if entity_type:
            query = query.filter(SavedFilter.entity_type == entity_type)
        query = query.order_by(SavedFilter.created_at.desc())
        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def create_filter(self, actor: User, data: dict) -> SavedFilter:
        sf = SavedFilter(
            organization_id=actor.organization_id,
            user_id=actor.id,
            name=data["name"],
            entity_type=data.get("entity_type", "lead"),
            definition=data["definition"],
            is_shared=data.get("is_shared", False),
        )
        self.db.add(sf)
        await self.db.flush()
        await self.db.refresh(sf)
        return sf

    async def _get_owned(self, actor: User, filter_id: uuid.UUID) -> SavedFilter:
        res = await self.db.execute(
            select(SavedFilter).filter(
                SavedFilter.id == filter_id,
                SavedFilter.organization_id == actor.organization_id,
                SavedFilter.is_deleted == False,
            )
        )
        sf = res.scalars().first()
        if not sf:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved filter not found")
        if sf.user_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only modify your own saved filters")
        return sf

    async def update_filter(self, actor: User, filter_id: uuid.UUID, data: dict) -> SavedFilter:
        sf = await self._get_owned(actor, filter_id)
        for key, val in data.items():
            setattr(sf, key, val)
        self.db.add(sf)
        await self.db.flush()
        await self.db.refresh(sf)
        return sf

    async def delete_filter(self, actor: User, filter_id: uuid.UUID) -> None:
        sf = await self._get_owned(actor, filter_id)
        sf.is_deleted = True
        self.db.add(sf)
        await self.db.flush()

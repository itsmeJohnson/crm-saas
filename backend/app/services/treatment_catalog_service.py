from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.treatment_catalog import TreatmentCatalogItem
from app.models.user import User


class TreatmentCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, actor: User, category: str | None = None, active_only: bool = False,
                   search: str | None = None) -> list[TreatmentCatalogItem]:
        q = select(TreatmentCatalogItem).filter(
            TreatmentCatalogItem.organization_id == actor.organization_id,
            TreatmentCatalogItem.is_deleted == False)
        if category:
            q = q.filter(TreatmentCatalogItem.category == category)
        if active_only:
            q = q.filter(TreatmentCatalogItem.is_active == True)
        if search:
            like = f"%{search.lower()}%"
            from sqlalchemy import func, or_
            q = q.filter(or_(func.lower(TreatmentCatalogItem.name).like(like),
                             func.lower(TreatmentCatalogItem.code).like(like)))
        q = q.order_by(TreatmentCatalogItem.category, TreatmentCatalogItem.name)
        return list((await self.db.execute(q)).scalars().all())

    async def categories(self, actor: User) -> list[str]:
        from sqlalchemy import distinct
        rows = (await self.db.execute(
            select(distinct(TreatmentCatalogItem.category)).filter(
                TreatmentCatalogItem.organization_id == actor.organization_id,
                TreatmentCatalogItem.is_deleted == False,
                TreatmentCatalogItem.category.isnot(None)))).scalars().all()
        return sorted([c for c in rows if c])

    async def get(self, actor: User, item_id: uuid.UUID) -> TreatmentCatalogItem:
        item = (await self.db.execute(select(TreatmentCatalogItem).filter(
            TreatmentCatalogItem.id == item_id,
            TreatmentCatalogItem.organization_id == actor.organization_id,
            TreatmentCatalogItem.is_deleted == False))).scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
        return item

    async def create(self, actor: User, data: dict) -> TreatmentCatalogItem:
        item = TreatmentCatalogItem(organization_id=actor.organization_id, created_by=actor.id, **data)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update(self, actor: User, item_id: uuid.UUID, data: dict) -> TreatmentCatalogItem:
        item = await self.get(actor, item_id)
        for k, v in data.items():
            setattr(item, k, v)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete(self, actor: User, item_id: uuid.UUID) -> None:
        item = await self.get(actor, item_id)
        item.is_deleted = True
        item.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

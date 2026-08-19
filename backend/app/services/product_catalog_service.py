from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_catalog import ProductCatalogItem
from app.models.user import User


class ProductCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, actor: User, category: str | None = None, active_only: bool = False,
                   search: str | None = None) -> list[ProductCatalogItem]:
        q = select(ProductCatalogItem).filter(
            ProductCatalogItem.organization_id == actor.organization_id,
            ProductCatalogItem.is_deleted == False)
        if category:
            q = q.filter(ProductCatalogItem.category == category)
        if active_only:
            q = q.filter(ProductCatalogItem.is_active == True)
        if search:
            like = f"%{search.lower()}%"
            from sqlalchemy import func, or_
            q = q.filter(or_(func.lower(ProductCatalogItem.name).like(like),
                             func.lower(ProductCatalogItem.code).like(like)))
        q = q.order_by(ProductCatalogItem.category, ProductCatalogItem.name)
        return list((await self.db.execute(q)).scalars().all())

    async def categories(self, actor: User) -> list[str]:
        from sqlalchemy import distinct
        rows = (await self.db.execute(
            select(distinct(ProductCatalogItem.category)).filter(
                ProductCatalogItem.organization_id == actor.organization_id,
                ProductCatalogItem.is_deleted == False,
                ProductCatalogItem.category.isnot(None)))).scalars().all()
        return sorted([c for c in rows if c])

    async def get(self, actor: User, item_id: uuid.UUID) -> ProductCatalogItem:
        item = (await self.db.execute(select(ProductCatalogItem).filter(
            ProductCatalogItem.id == item_id,
            ProductCatalogItem.organization_id == actor.organization_id,
            ProductCatalogItem.is_deleted == False))).scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")
        return item

    async def create(self, actor: User, data: dict) -> ProductCatalogItem:
        item = ProductCatalogItem(organization_id=actor.organization_id, created_by=actor.id, **data)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update(self, actor: User, item_id: uuid.UUID, data: dict) -> ProductCatalogItem:
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

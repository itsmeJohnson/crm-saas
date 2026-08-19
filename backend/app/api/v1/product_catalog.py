import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user, require_role, require_module
from app.schemas.product_catalog import (
    ProductCatalogCreate, ProductCatalogUpdate, ProductCatalogResponse,
)
from app.services.product_catalog_service import ProductCatalogService

router = APIRouter(dependencies=[Depends(require_module("billing"))])
_admin = require_role(["OrgAdmin", "Manager"])
_rw = require_active_user  # any active user can read the catalog/price list


@router.get("/", response_model=List[ProductCatalogResponse])
async def list_products(actor: Annotated[User, Depends(_rw)], db: Annotated[AsyncSession, Depends(get_db)],
                        category: str | None = Query(None), active_only: bool = Query(False),
                        search: str | None = Query(None)):
    return await ProductCatalogService(db).list(actor, category=category, active_only=active_only, search=search)


@router.get("/categories", response_model=List[str])
async def list_categories(actor: Annotated[User, Depends(_rw)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductCatalogService(db).categories(actor)


@router.post("/", response_model=ProductCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_product(req: ProductCatalogCreate, actor: Annotated[User, Depends(_admin)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductCatalogService(db).create(actor, req.model_dump())


@router.get("/{item_id}", response_model=ProductCatalogResponse)
async def get_product(item_id: uuid.UUID, actor: Annotated[User, Depends(_rw)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductCatalogService(db).get(actor, item_id)


@router.patch("/{item_id}", response_model=ProductCatalogResponse)
async def update_product(item_id: uuid.UUID, req: ProductCatalogUpdate, actor: Annotated[User, Depends(_admin)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductCatalogService(db).update(actor, item_id, req.model_dump(exclude_unset=True))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(item_id: uuid.UUID, actor: Annotated[User, Depends(_admin)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    await ProductCatalogService(db).delete(actor, item_id)

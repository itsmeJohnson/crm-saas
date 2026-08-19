import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user, require_role, require_module
from app.schemas.treatment_catalog import (
    TreatmentCatalogCreate, TreatmentCatalogUpdate, TreatmentCatalogResponse,
)
from app.services.treatment_catalog_service import TreatmentCatalogService

router = APIRouter(dependencies=[Depends(require_module("treatments"))])
_admin = require_role(["OrgAdmin", "Manager"])
_rw = require_active_user  # any active user can read the price list


@router.get("/", response_model=List[TreatmentCatalogResponse])
async def list_treatments(actor: Annotated[User, Depends(_rw)], db: Annotated[AsyncSession, Depends(get_db)],
                          category: str | None = Query(None), active_only: bool = Query(False),
                          search: str | None = Query(None)):
    return await TreatmentCatalogService(db).list(actor, category=category, active_only=active_only, search=search)


@router.get("/categories", response_model=List[str])
async def list_categories(actor: Annotated[User, Depends(_rw)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TreatmentCatalogService(db).categories(actor)


@router.post("/", response_model=TreatmentCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_treatment(req: TreatmentCatalogCreate, actor: Annotated[User, Depends(_admin)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await TreatmentCatalogService(db).create(actor, req.model_dump())


@router.get("/{item_id}", response_model=TreatmentCatalogResponse)
async def get_treatment(item_id: uuid.UUID, actor: Annotated[User, Depends(_rw)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await TreatmentCatalogService(db).get(actor, item_id)


@router.patch("/{item_id}", response_model=TreatmentCatalogResponse)
async def update_treatment(item_id: uuid.UUID, req: TreatmentCatalogUpdate, actor: Annotated[User, Depends(_admin)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await TreatmentCatalogService(db).update(actor, item_id, req.model_dump(exclude_unset=True))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_treatment(item_id: uuid.UUID, actor: Annotated[User, Depends(_admin)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    await TreatmentCatalogService(db).delete(actor, item_id)

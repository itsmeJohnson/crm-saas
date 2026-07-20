import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.branch import (
    TerritoryCreate, TerritoryUpdate, TerritoryResponse, TerritoryTreeNode, LocationsResponse,
    TerritoryAnalyticsRow,
)
from app.services.branch_territory_service import BranchTerritoryService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (before /{id}) ----------
@router.get("/tree", response_model=List[TerritoryTreeNode])
async def tree(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).territory_tree(actor)


@router.get("/locations", response_model=LocationsResponse)
async def locations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).locations(actor)


@router.get("/analytics", response_model=List[TerritoryAnalyticsRow])
async def analytics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None)):
    return await BranchTerritoryService(db).territory_analytics(actor, date_from=date_from, date_to=date_to)


# ---------- CRUD ----------
@router.get("", response_model=List[TerritoryResponse])
async def list_territories(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None), level: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"), parent_id: uuid.UUID | None = Query(None),
):
    return await BranchTerritoryService(db).list_territories(actor, search=search, level=level,
                                                             status_filter=status_filter, parent_id=parent_id)


@router.post("", response_model=TerritoryResponse, status_code=status.HTTP_201_CREATED)
async def create_territory(req: TerritoryCreate, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).create_territory(actor, req.model_dump())


@router.patch("/{territory_id}", response_model=TerritoryResponse)
async def update_territory(territory_id: uuid.UUID, req: TerritoryUpdate,
                           actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).update_territory(actor, territory_id, req.model_dump(exclude_unset=True))


@router.delete("/{territory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_territory(territory_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    await BranchTerritoryService(db).delete_territory(actor, territory_id)

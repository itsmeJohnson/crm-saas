import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.branch import (
    BranchCreate, BranchUpdate, BranchResponse, BranchList, PincodeUpsert, PincodeResponse, PincodeList,
    LeadAssignRequest, LeadAssignResult, BranchDashboardResponse, BranchPerformanceResponse,
    BranchAnalyticsRow, ImportResult,
)
from app.services.branch_territory_service import BranchTerritoryService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (before /{id}) ----------
@router.get("/dashboard", response_model=BranchDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).dashboard(actor)


@router.get("/analytics", response_model=List[BranchAnalyticsRow])
async def analytics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None)):
    return await BranchTerritoryService(db).branch_analytics(actor, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    csv_text = await BranchTerritoryService(db).export_branches(actor)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=branches.csv"})


# ---------- PIN-code mapping ----------
@router.get("/pincodes", response_model=PincodeList)
async def list_pincodes(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                        search: str | None = Query(None), territory_id: uuid.UUID | None = Query(None),
                        skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)):
    return await BranchTerritoryService(db).list_pincodes(actor, search=search, territory_id=territory_id,
                                                          skip=skip, limit=limit)


@router.post("/pincodes", response_model=PincodeResponse)
async def upsert_pincode(req: PincodeUpsert, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).upsert_pincode(actor, req.model_dump())


@router.post("/pincodes/import", response_model=ImportResult)
async def import_pincodes(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          file: UploadFile = File(...)):
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds the 2MB limit")
    result = await BranchTerritoryService(db).import_pincodes(actor, content)
    await db.commit()
    return result


@router.delete("/pincodes/{pincode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pincode(pincode_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    await BranchTerritoryService(db).delete_pincode(actor, pincode_id)


# ---------- Lead territory assignment ----------
@router.post("/assign-leads", response_model=LeadAssignResult)
async def assign_leads(req: LeadAssignRequest, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).assign_leads(
        actor, req.lead_ids, branch_id=req.branch_id, territory_id=req.territory_id, auto=req.auto)


# ---------- CRUD ----------
@router.get("", response_model=BranchList)
async def list_branches(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    territory_id: uuid.UUID | None = Query(None), city: str | None = Query(None),
    manager_id: uuid.UUID | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
):
    return await BranchTerritoryService(db).list_branches(actor, search=search, status_filter=status_filter,
                                                          territory_id=territory_id, city=city,
                                                          manager_id=manager_id, skip=skip, limit=limit)


@router.post("", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(req: BranchCreate, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).create_branch(actor, req.model_dump())


@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(branch_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).get_branch(actor, branch_id)


@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch(branch_id: uuid.UUID, req: BranchUpdate,
                        actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await BranchTerritoryService(db).update_branch(actor, branch_id, req.model_dump(exclude_unset=True))


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    await BranchTerritoryService(db).delete_branch(actor, branch_id)


@router.get("/{branch_id}/performance", response_model=BranchPerformanceResponse)
async def branch_performance(branch_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)],
                             date_from: datetime | None = Query(None), date_to: datetime | None = Query(None)):
    return await BranchTerritoryService(db).branch_performance(actor, branch_id, date_from=date_from, date_to=date_to)

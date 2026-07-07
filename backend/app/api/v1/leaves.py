import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.leave import (
    LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeResponse, AllocationRequest, BalanceRow,
    LeaveApplyRequest, LeaveReviewRequest, LeaveRequestResponse, RequestList, LeaveCalendarItem,
    LeaveDashboardResponse, LeaveReportResponse,
)
from app.services.leave_service import LeaveService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Dashboard / calendar / report ----------
@router.get("/dashboard", response_model=LeaveDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).dashboard(actor)


@router.get("/calendar", response_model=List[LeaveCalendarItem])
async def calendar(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date = Query(...), date_to: date = Query(...)):
    return await LeaveService(db).calendar(actor, date_from, date_to)


@router.get("/report", response_model=LeaveReportResponse)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 year: int = Query(...), user_id: uuid.UUID | None = Query(None)):
    return await LeaveService(db).report(actor, year, user_id=user_id)


# ---------- Leave types ----------
@router.get("/types", response_model=List[LeaveTypeResponse])
async def list_types(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     status_filter: str | None = Query(None, alias="status")):
    return await LeaveService(db).list_types(actor, status_filter=status_filter)


@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_type(req: LeaveTypeCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).create_type(actor, req.model_dump())


@router.patch("/types/{type_id}", response_model=LeaveTypeResponse)
async def update_type(type_id: uuid.UUID, req: LeaveTypeUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).update_type(actor, type_id, req.model_dump(exclude_unset=True))


@router.delete("/types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_type(type_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await LeaveService(db).delete_type(actor, type_id)


# ---------- Balances ----------
@router.get("/balances", response_model=List[BalanceRow])
async def balances(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   user_id: uuid.UUID | None = Query(None), year: int | None = Query(None)):
    return await LeaveService(db).balances(actor, user_id or actor.id, year=year)


@router.post("/balances/allocate", response_model=BalanceRow)
async def allocate(req: AllocationRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).set_allocation(actor, req.model_dump())


# ---------- Requests ----------
@router.get("/requests", response_model=RequestList)
async def list_requests(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                        scope: str = Query("mine"), status_filter: str | None = Query(None, alias="status"),
                        request_type: str | None = Query(None), date_from: date | None = Query(None),
                        date_to: date | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    return await LeaveService(db).list_requests(actor, scope=scope, status_filter=status_filter,
                                                request_type=request_type, date_from=date_from,
                                                date_to=date_to, skip=skip, limit=limit)


@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def apply_leave(req: LeaveApplyRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).apply(actor, req.model_dump())


@router.post("/requests/{request_id}/review", response_model=LeaveRequestResponse)
async def review(request_id: uuid.UUID, req: LeaveReviewRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).review(actor, request_id, req.approve, note=req.note)


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
async def cancel(request_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await LeaveService(db).cancel(actor, request_id)

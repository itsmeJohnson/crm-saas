import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.attendance import (
    ShiftCreate, ShiftUpdate, ShiftResponse, ShiftAssignRequest, ShiftAssignmentRow, AssignResult,
    ClockRequest, BreakStartRequest, BiometricPunchRequest, AttendanceRecordResponse, RecordList,
    MyTodayResponse, CorrectionRequest, CorrectionReview, CorrectionResponse,
    AttendanceDashboardResponse, MonthlyReportResponse,
)
from app.services.attendance_service import AttendanceService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Self clock / break ----------
@router.get("/me/today", response_model=MyTodayResponse)
async def my_today(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).my_today(actor)


@router.post("/clock-in", response_model=AttendanceRecordResponse)
async def clock_in(req: ClockRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).clock_in(actor, latitude=req.latitude, longitude=req.longitude)


@router.post("/clock-out", response_model=AttendanceRecordResponse)
async def clock_out(req: ClockRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).clock_out(actor, latitude=req.latitude, longitude=req.longitude)


@router.post("/break/start", response_model=AttendanceRecordResponse)
async def break_start(req: BreakStartRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).break_start(actor, reason=req.reason)


@router.post("/break/end", response_model=AttendanceRecordResponse)
async def break_end(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).break_end(actor)


@router.post("/biometric/punch", response_model=AttendanceRecordResponse)
async def biometric_punch(req: BiometricPunchRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).biometric_punch(actor, req.model_dump())


# ---------- Dashboard / reports ----------
@router.get("/dashboard", response_model=AttendanceDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).dashboard(actor)


@router.get("/report/monthly", response_model=MonthlyReportResponse)
async def monthly_report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         year: int = Query(...), month: int = Query(..., ge=1, le=12),
                         user_id: uuid.UUID | None = Query(None)):
    return await AttendanceService(db).monthly_report(actor, year, month, user_id=user_id)


@router.get("/records", response_model=RecordList)
async def list_records(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                       user_id: uuid.UUID | None = Query(None), date_from: date | None = Query(None),
                       date_to: date | None = Query(None), status_filter: str | None = Query(None, alias="status"),
                       skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    return await AttendanceService(db).list_records(actor, user_id=user_id, date_from=date_from,
                                                    date_to=date_to, status_filter=status_filter, skip=skip, limit=limit)


# ---------- Shifts ----------
@router.get("/shifts", response_model=List[ShiftResponse])
async def list_shifts(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      status_filter: str | None = Query(None, alias="status")):
    return await AttendanceService(db).list_shifts(actor, status_filter=status_filter)


@router.post("/shifts", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(req: ShiftCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).create_shift(actor, req.model_dump())


@router.patch("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(shift_id: uuid.UUID, req: ShiftUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).update_shift(actor, shift_id, req.model_dump(exclude_unset=True))


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(shift_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await AttendanceService(db).delete_shift(actor, shift_id)


@router.post("/shifts/assign", response_model=AssignResult)
async def assign_shift(req: ShiftAssignRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).assign_shift(actor, req.model_dump())


@router.get("/users/{user_id}/assignments", response_model=List[ShiftAssignmentRow])
async def user_assignments(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).user_assignments(actor, user_id)


# ---------- Corrections & approvals ----------
@router.get("/corrections", response_model=List[CorrectionResponse])
async def list_corrections(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                           status_filter: str | None = Query(None, alias="status"), mine: bool = Query(False)):
    return await AttendanceService(db).list_corrections(actor, status_filter=status_filter, mine=mine)


@router.post("/corrections", response_model=CorrectionResponse, status_code=status.HTTP_201_CREATED)
async def request_correction(req: CorrectionRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).request_correction(actor, req.model_dump())


@router.post("/corrections/{correction_id}/review", response_model=CorrectionResponse)
async def review_correction(correction_id: uuid.UUID, req: CorrectionReview,
                            actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AttendanceService(db).review_correction(actor, correction_id, req.approve, note=req.note)

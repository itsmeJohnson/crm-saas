import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.shift import (
    ShiftCreate, ShiftUpdate, ShiftResponse, ShiftAssignReq, AssignResult, PresetResult,
    RotationCreate, RotationUpdate, RotationResponse, RotationAssignReq, RotationMemberRow,
    ShiftCalendarItem, ShiftAttendanceResponse, ShiftReportRow, ShiftDashboardResponse,
)
from app.services.shift_service import ShiftService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Dashboard / calendar / reports ----------
@router.get("/dashboard", response_model=ShiftDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).dashboard(actor)


@router.get("/calendar", response_model=List[ShiftCalendarItem])
async def calendar(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date = Query(...), date_to: date = Query(...), user_id: uuid.UUID | None = Query(None)):
    return await ShiftService(db).calendar(actor, date_from, date_to, user_id=user_id)


@router.get("/reports", response_model=List[ShiftReportRow])
async def reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  date_from: date = Query(...), date_to: date = Query(...)):
    return await ShiftService(db).reports(actor, date_from, date_to)


# ---------- Rotations (static prefix before /{shift_id}) ----------
@router.get("/rotations", response_model=List[RotationResponse])
async def list_rotations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         status_filter: str | None = Query(None, alias="status")):
    return await ShiftService(db).list_rotations(actor, status_filter=status_filter)


@router.post("/rotations", response_model=RotationResponse, status_code=status.HTTP_201_CREATED)
async def create_rotation(req: RotationCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump()
    payload["shift_sequence"] = [str(x) for x in payload["shift_sequence"]]
    return await ShiftService(db).create_rotation(actor, payload)


@router.patch("/rotations/{rotation_id}", response_model=RotationResponse)
async def update_rotation(rotation_id: uuid.UUID, req: RotationUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump(exclude_unset=True)
    if "shift_sequence" in payload and payload["shift_sequence"] is not None:
        payload["shift_sequence"] = [str(x) for x in payload["shift_sequence"]]
    return await ShiftService(db).update_rotation(actor, rotation_id, payload)


@router.delete("/rotations/{rotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rotation(rotation_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await ShiftService(db).delete_rotation(actor, rotation_id)


@router.post("/rotations/{rotation_id}/assign", response_model=AssignResult)
async def assign_rotation(rotation_id: uuid.UUID, req: RotationAssignReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).assign_rotation(actor, rotation_id, req.model_dump())


@router.get("/rotations/{rotation_id}/members", response_model=List[RotationMemberRow])
async def rotation_members(rotation_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).rotation_members(actor, rotation_id)


@router.post("/rotations/{rotation_id}/members/remove", response_model=dict)
async def remove_rotation_member(rotation_id: uuid.UUID, user_id: uuid.UUID = Query(...),
                                 actor: Annotated[User, Depends(require_active_user)] = None,
                                 db: Annotated[AsyncSession, Depends(get_db)] = None):
    return await ShiftService(db).remove_rotation_member(actor, rotation_id, user_id)


# ---------- Shift attendance ----------
@router.get("/{shift_id}/attendance", response_model=ShiftAttendanceResponse)
async def shift_attendance(shift_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                           date_from: date = Query(...), date_to: date = Query(...)):
    return await ShiftService(db).shift_attendance(actor, shift_id, date_from, date_to)


# ---------- Shifts CRUD + assignment ----------
@router.get("", response_model=List[ShiftResponse])
async def list_shifts(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      status_filter: str | None = Query(None, alias="status"), shift_type: str | None = Query(None)):
    return await ShiftService(db).list_shifts(actor, status_filter=status_filter, shift_type=shift_type)


@router.post("", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(req: ShiftCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).create_shift(actor, req.model_dump())


@router.post("/presets", response_model=PresetResult)
async def create_presets(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).create_presets(actor)


@router.post("/assign", response_model=AssignResult)
async def assign_shift(req: ShiftAssignReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).assign_shift(actor, req.model_dump())


@router.patch("/{shift_id}", response_model=ShiftResponse)
async def update_shift(shift_id: uuid.UUID, req: ShiftUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ShiftService(db).update_shift(actor, shift_id, req.model_dump(exclude_unset=True))


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(shift_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await ShiftService(db).delete_shift(actor, shift_id)

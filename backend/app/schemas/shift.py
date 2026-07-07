import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------- Shifts ----------
class ShiftCreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=30)
    shift_type: str = Field("general", pattern="^(morning|evening|night|flexible|general)$")
    start_time: str = Field(..., description="HH:MM")
    end_time: str = Field(..., description="HH:MM")
    break_minutes: int = Field(0, ge=0)
    grace_minutes: int = Field(0, ge=0)
    working_days: list[str] | None = None
    is_night_shift: bool | None = None
    is_flexible: bool | None = None
    works_on_holidays: bool = False
    status: str = Field("active", pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class ShiftUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    code: str | None = Field(None, max_length=30)
    shift_type: str | None = Field(None, pattern="^(morning|evening|night|flexible|general)$")
    start_time: str | None = None
    end_time: str | None = None
    break_minutes: int | None = Field(None, ge=0)
    grace_minutes: int | None = Field(None, ge=0)
    working_days: list[str] | None = None
    is_night_shift: bool | None = None
    is_flexible: bool | None = None
    works_on_holidays: bool | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class ShiftResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    shift_type: str
    start_time: str
    end_time: str
    break_minutes: int
    grace_minutes: int
    working_days: list[str]
    is_night_shift: bool
    is_flexible: bool
    works_on_holidays: bool
    status: str
    color: str | None = None
    created_at: datetime


class ShiftAssignReq(BaseModel):
    shift_id: uuid.UUID
    user_ids: list[uuid.UUID] = Field(..., min_length=1)
    start_date: date | None = None
    end_date: date | None = None


class AssignResult(BaseModel):
    assigned: int


class PresetResult(BaseModel):
    created: int


# ---------- Rotations ----------
class RotationCreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=300)
    shift_sequence: list[uuid.UUID] = Field(..., min_length=2)
    rotation_days: int = Field(7, ge=1)
    status: str = Field("active", pattern="^(active|archived)$")


class RotationUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=300)
    shift_sequence: list[uuid.UUID] | None = Field(None, min_length=2)
    rotation_days: int | None = Field(None, ge=1)
    status: str | None = Field(None, pattern="^(active|archived)$")


class RotationResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    description: str | None = None
    shift_sequence: list[str]
    shift_names: list[str]
    rotation_days: int
    status: str
    member_count: int
    created_at: datetime


class RotationAssignReq(BaseModel):
    user_ids: list[uuid.UUID] = Field(..., min_length=1)
    anchor_date: date | None = None
    end_date: date | None = None


class RotationMemberRow(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    anchor_date: str
    end_date: str | None = None


# ---------- Calendar / attendance / reports ----------
class ShiftCalendarItem(BaseModel):
    user_id: str
    user_name: str | None = None
    date: str
    shift_id: str | None = None
    shift_name: str | None = None
    shift_type: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    state: str  # working|weekly_off|holiday


class ShiftAttendanceRow(BaseModel):
    user_id: str
    user_name: str | None = None
    work_date: str
    status: str
    is_late: bool
    late_minutes: int
    is_early_logout: bool
    worked_minutes: int


class ShiftAttendanceResponse(BaseModel):
    shift_id: str
    shift_name: str
    records: list[ShiftAttendanceRow]


class ShiftReportRow(BaseModel):
    shift_id: str
    shift_name: str
    shift_type: str
    assigned: int
    records: int
    present: int
    late: int
    early_logout: int
    on_leave: int
    worked_hours: float


class ShiftDashboardResponse(BaseModel):
    total_shifts: int
    flexible_shifts: int
    night_shifts: int
    active_rotations: int
    by_type: dict[str, int]
    my_shift_today: ShiftResponse | None = None

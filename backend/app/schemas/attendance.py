import uuid
from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, Field


# ---------- Shifts ----------
class ShiftCreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=30)
    start_time: str = Field(..., description="HH:MM")
    end_time: str = Field(..., description="HH:MM")
    break_minutes: int = Field(0, ge=0)
    grace_minutes: int = Field(0, ge=0)
    working_days: list[str] | None = None
    is_night_shift: bool | None = None
    status: str = Field("active", pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class ShiftUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    code: str | None = Field(None, max_length=30)
    start_time: str | None = None
    end_time: str | None = None
    break_minutes: int | None = Field(None, ge=0)
    grace_minutes: int | None = Field(None, ge=0)
    working_days: list[str] | None = None
    is_night_shift: bool | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class ShiftResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    start_time: str
    end_time: str
    break_minutes: int
    grace_minutes: int
    working_days: list[str]
    is_night_shift: bool
    status: str
    color: str | None = None
    created_at: datetime


class ShiftAssignRequest(BaseModel):
    shift_id: uuid.UUID
    user_ids: list[uuid.UUID] = Field(..., min_length=1)
    start_date: date | None = None
    end_date: date | None = None


class ShiftAssignmentRow(BaseModel):
    id: str
    shift_id: str
    shift_name: str | None = None
    start_date: str
    end_date: str | None = None


# ---------- Clock / break ----------
class ClockRequest(BaseModel):
    latitude: float | None = None
    longitude: float | None = None


class BreakStartRequest(BaseModel):
    reason: str | None = Field(None, max_length=200)


class BiometricPunchRequest(BaseModel):
    user_id: uuid.UUID | None = None
    email: str | None = None
    type: str = Field(..., pattern="^(in|out)$")
    timestamp: datetime | None = None
    device_id: str | None = Field(None, max_length=100)
    latitude: float | None = None
    longitude: float | None = None


# ---------- Records ----------
class AttendanceRecordResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    work_date: str
    shift_id: str | None = None
    clock_in_at: str | None = None
    clock_out_at: str | None = None
    status: str
    is_late: bool
    late_minutes: int
    is_early_logout: bool
    early_minutes: int
    worked_minutes: int
    break_minutes: int
    in_latitude: float | None = None
    in_longitude: float | None = None
    source: str
    notes: str | None = None


class RecordList(BaseModel):
    items: list[AttendanceRecordResponse]
    total: int


class MyTodayResponse(BaseModel):
    work_date: str
    record: AttendanceRecordResponse | None = None
    shift: ShiftResponse | None = None
    on_break: bool


# ---------- Corrections ----------
class CorrectionRequest(BaseModel):
    user_id: uuid.UUID | None = None
    work_date: date
    reason: str = Field(..., max_length=500)
    proposed: dict[str, Any] | None = None  # {clock_in_at, clock_out_at, status, notes}


class CorrectionReview(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=500)


class CorrectionResponse(BaseModel):
    id: str
    attendance_id: str | None = None
    user_id: str
    user_name: str | None = None
    work_date: str
    reason: str
    proposed: dict | None = None
    status: str
    requested_by: str
    requested_by_name: str | None = None
    reviewed_by_name: str | None = None
    review_note: str | None = None
    created_at: datetime


# ---------- Dashboard / report ----------
class AttendanceDashboardResponse(BaseModel):
    work_date: str
    headcount: int
    present: int
    absent: int
    late: int
    on_break: int
    clocked_out: int
    still_working: int
    pending_corrections: int


class MonthlyReportRow(BaseModel):
    user_id: str
    name: str
    present_days: int
    late_days: int
    early_days: int
    half_days: int
    leave_days: int
    worked_minutes: int
    break_minutes: int
    worked_hours: float
    break_hours: float


class MonthlyReportResponse(BaseModel):
    year: int
    month: int
    working_days_in_month: int
    rows: list[MonthlyReportRow]


class AssignResult(BaseModel):
    assigned: int

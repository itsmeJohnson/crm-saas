import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------- Leave types ----------
class LeaveTypeCreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=300)
    is_paid: bool = True
    annual_quota: float = Field(0, ge=0)
    max_consecutive_days: int | None = Field(None, ge=1)
    allow_half_day: bool = True
    requires_approval: bool = True
    deducts_balance: bool = True
    color: str | None = Field(None, max_length=20)
    status: str = Field("active", pattern="^(active|archived)$")


class LeaveTypeUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=300)
    is_paid: bool | None = None
    annual_quota: float | None = Field(None, ge=0)
    max_consecutive_days: int | None = Field(None, ge=1)
    allow_half_day: bool | None = None
    requires_approval: bool | None = None
    deducts_balance: bool | None = None
    color: str | None = Field(None, max_length=20)
    status: str | None = Field(None, pattern="^(active|archived)$")


class LeaveTypeResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    description: str | None = None
    is_paid: bool
    annual_quota: float
    max_consecutive_days: int | None = None
    allow_half_day: bool
    requires_approval: bool
    deducts_balance: bool
    color: str | None = None
    status: str
    created_at: datetime


# ---------- Balances ----------
class AllocationRequest(BaseModel):
    user_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int | None = None
    allocated: float = Field(..., ge=0)
    carried_forward: float | None = Field(None, ge=0)


class BalanceRow(BaseModel):
    leave_type_id: str
    leave_type_name: str
    color: str | None = None
    year: int
    allocated: float
    carried_forward: float
    used: float
    pending: float
    available: float


# ---------- Requests ----------
class LeaveApplyRequest(BaseModel):
    user_id: uuid.UUID | None = None
    request_type: str = Field("leave", pattern="^(leave|wfh)$")
    leave_type_id: uuid.UUID | None = None
    start_date: date
    end_date: date
    is_half_day: bool = False
    half_day_period: str | None = Field(None, pattern="^(first_half|second_half)$")
    reason: str | None = Field(None, max_length=500)


class LeaveReviewRequest(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=500)


class LeaveRequestResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    request_type: str
    leave_type_id: str | None = None
    leave_type_name: str | None = None
    start_date: str
    end_date: str
    is_half_day: bool
    half_day_period: str | None = None
    day_count: float
    reason: str | None = None
    status: str
    reviewed_by_name: str | None = None
    review_note: str | None = None
    created_at: datetime


class RequestList(BaseModel):
    items: list[LeaveRequestResponse]
    total: int


class LeaveCalendarItem(BaseModel):
    type: str
    id: str
    user_id: str | None = None
    user_name: str | None = None
    request_type: str
    leave_type_name: str | None = None
    start_date: str
    end_date: str
    is_half_day: bool
    day_count: float
    status: str


class LeaveDashboardResponse(BaseModel):
    my_pending: int
    my_available_days: float
    pending_approvals: int
    on_leave_today: list[dict]


class LeaveReportResponse(BaseModel):
    year: int
    rows: list[dict]

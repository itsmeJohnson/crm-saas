import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------- Chains ----------
class ChainStep(BaseModel):
    level: int | None = None
    approver_role: str | None = Field(None, pattern="^(Manager|OrgAdmin|SuperAdmin)$")
    approver_user_id: uuid.UUID | None = None


class ChainCreate(BaseModel):
    name: str = Field(..., max_length=150)
    request_type: str
    min_amount: float = Field(0, ge=0)
    steps: list[ChainStep] = Field(..., min_length=1)
    escalation_hours: int | None = Field(None, ge=1)
    is_active: bool = True


class ChainUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    min_amount: float | None = Field(None, ge=0)
    steps: list[ChainStep] | None = None
    escalation_hours: int | None = Field(None, ge=1)
    is_active: bool | None = None


class ChainResponse(BaseModel):
    id: str
    name: str
    request_type: str
    min_amount: float
    steps: list[dict]
    escalation_hours: int | None = None
    is_active: bool
    created_at: datetime


# ---------- Requests ----------
class RequestCreate(BaseModel):
    request_type: str
    title: str = Field(..., max_length=200)
    description: str | None = None
    amount: float | None = Field(None, ge=0)
    reference_type: str | None = Field(None, max_length=50)
    reference_id: str | None = Field(None, max_length=64)
    payload: dict[str, Any] | None = None


class ActRequest(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=500)


class RequestResponse(BaseModel):
    id: str
    request_type: str
    title: str
    description: str | None = None
    amount: float | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    payload: dict | None = None
    current_level: int
    total_levels: int
    status: str
    escalated: bool
    requested_by: str
    requested_by_name: str | None = None
    created_at: datetime
    decided_at: str | None = None


class RequestList(BaseModel):
    items: list[RequestResponse]
    total: int


class HistoryRow(BaseModel):
    id: str
    level: int
    action: str
    actor_name: str | None = None
    on_behalf_of_name: str | None = None
    note: str | None = None
    created_at: str | None = None


# ---------- Delegation ----------
class DelegationCreate(BaseModel):
    delegate_id: uuid.UUID
    request_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class DelegationResponse(BaseModel):
    id: str
    delegator_id: str
    delegate_id: str
    request_type: str | None = None
    start_date: str
    end_date: str | None = None
    is_active: bool
    created_at: datetime


# ---------- Dashboard / reports ----------
class ApprovalDashboardResponse(BaseModel):
    my_pending: int
    awaiting_my_action: int
    total: int
    approved: int
    rejected: int
    pending: int


class ApprovalReportResponse(BaseModel):
    rows: list[dict]


class EscalateResult(BaseModel):
    escalated: int

import uuid
from datetime import date
from pydantic import BaseModel, Field


class TargetRow(BaseModel):
    id: str
    scope: str  # individual|team|department
    scope_name: str | None = None
    name: str
    metric: str | None = None
    unit: str
    period: str
    target_value: float
    actual: float
    attainment: float
    achieved: bool
    status_label: str  # on_track|at_risk|achieved|missed
    start_date: str
    end_date: str
    status: str


class TargetDashboardResponse(BaseModel):
    total: int
    achieved: int
    on_track: int
    at_risk: int
    missed: int
    avg_attainment: float
    by_scope: dict[str, int]
    by_period: dict[str, int]
    at_risk_targets: list[dict]


class TargetReportResponse(BaseModel):
    rows: list[TargetRow]
    count: int


class TargetCreateRequest(BaseModel):
    scope: str = Field(..., pattern="^(individual|team|department)$")
    period: str = Field("monthly", pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    target_value: float = Field(..., ge=0)
    start_date: date | None = None
    end_date: date | None = None
    # individual
    user_id: uuid.UUID | None = None
    kpi_id: uuid.UUID | None = None
    # team / department
    team_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    name: str | None = Field(None, max_length=150)
    metric: str | None = None


class TargetCreateResult(BaseModel):
    scope: str
    created: bool

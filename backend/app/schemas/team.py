import uuid
from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., max_length=150)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=500)
    team_leader_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    capacity: int | None = Field(None, ge=1)
    status: str = Field("active", pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class TeamUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    code: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=500)
    team_leader_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    capacity: int | None = Field(None, ge=1)
    status: str | None = Field(None, pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class TeamResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str | None = None
    description: str | None = None
    team_leader_id: str | None = None
    leader_name: str | None = None
    leader_email: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    capacity: int | None = None
    status: str
    color: str | None = None
    member_count: int
    created_at: datetime


class TeamList(BaseModel):
    items: list[TeamResponse]
    total: int


class TeamMemberItem(BaseModel):
    id: str
    membership_id: str
    name: str
    email: str
    role: str
    role_in_team: str
    is_active: bool
    joined_at: str | None = None


class MemberChangeRequest(BaseModel):
    user_ids: list[uuid.UUID]


class TeamTargetCreate(BaseModel):
    name: str = Field(..., max_length=150)
    metric: str
    target_value: float
    period: str = "monthly"
    start_date: date | None = None
    end_date: date | None = None


class TeamTargetResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    metric: str
    target_value: float
    period: str
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamPerformanceResponse(BaseModel):
    team_id: str
    name: str
    member_count: int
    capacity: int | None = None
    metrics: dict[str, Any]
    kpis: list[dict]
    members: list[dict]


class TeamDashboardResponse(BaseModel):
    total: int
    active: int
    archived: int
    total_members: int
    capacity_utilization: float | None = None
    largest: list[dict]


class TeamAnalyticsRow(BaseModel):
    team_id: str
    name: str
    member_count: int
    capacity: int | None = None
    leads_converted: int
    calls_made: int
    tasks_completed: int
    revenue: float
    activities: int


class TeamCalendarItem(BaseModel):
    type: str
    id: str
    title: str
    start: datetime | None = None
    end: datetime | None = None
    status: str
    event_type: str
    user_id: str | None = None
    user_name: str


class AssignWorkRequest(BaseModel):
    lead_ids: list[uuid.UUID] = []
    task_ids: list[uuid.UUID] = []
    strategy: str = Field("round_robin", pattern="^(round_robin|leader)$")


class AssignWorkResult(BaseModel):
    assigned: int
    distribution: dict[str, int]


class BulkTeamRequest(BaseModel):
    team_ids: list[uuid.UUID]
    action: str = Field(..., pattern="^(archive|activate|delete)$")


class BulkTeamResult(BaseModel):
    processed: int
    errors: list[dict]


class TeamImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[dict]


class TeamReportResponse(BaseModel):
    summary: TeamDashboardResponse
    teams: list[TeamAnalyticsRow]

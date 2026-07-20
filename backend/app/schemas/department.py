import uuid
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = Field(None, max_length=500)
    parent_department_id: Optional[uuid.UUID] = None
    head_user_id: Optional[uuid.UUID] = None
    status: str = "active"
    budget: Optional[float] = None
    budget_period: Optional[str] = Field(None, max_length=20)
    cost_center: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=20)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    code: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = Field(None, max_length=500)
    parent_department_id: Optional[uuid.UUID] = None
    head_user_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    budget: Optional[float] = None
    budget_period: Optional[str] = None
    cost_center: Optional[str] = None
    color: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_department_id: Optional[str] = None
    head_user_id: Optional[str] = None
    head_name: Optional[str] = None
    status: str
    budget: Optional[float] = None
    budget_period: Optional[str] = None
    cost_center: Optional[str] = None
    color: Optional[str] = None
    member_count: int
    created_at: datetime


class DepartmentList(BaseModel):
    items: List[DepartmentResponse]
    total: int


class DepartmentTreeNode(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    status: str
    head_user_id: Optional[str] = None
    member_count: int
    children: List["DepartmentTreeNode"] = []


class MemberItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool


class MemberAssignReq(BaseModel):
    user_ids: List[uuid.UUID] = Field(..., min_length=1)


class StatusReq(BaseModel):
    status: str


class TargetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    metric: str
    target_value: float
    period: str = "monthly"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    metric: str
    target_value: float
    period: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class KPIItem(BaseModel):
    target_id: str
    name: str
    metric: str
    target_value: float
    actual: float
    attainment: float
    period: str


class PerformanceResponse(BaseModel):
    department_id: str
    name: str
    member_count: int
    budget: Optional[float] = None
    metrics: dict
    kpis: List[KPIItem]


class DashboardResponse(BaseModel):
    total: int
    active: int
    archived: int
    total_budget: float
    unassigned_members: int
    largest: List[dict]


class AnalyticsRow(BaseModel):
    department_id: str
    name: str
    member_count: int
    budget: Optional[float] = None
    leads_converted: int
    calls_made: int
    tasks_completed: int
    revenue: float
    activities: int


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]

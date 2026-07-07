import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field


# ---------- Territory ----------
class TerritoryCreate(BaseModel):
    name: str = Field(..., max_length=150)
    code: str | None = Field(None, max_length=30)
    level: str = Field("region", pattern="^(region|zone|city|area)$")
    parent_id: uuid.UUID | None = None
    manager_user_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)
    status: str = Field("active", pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class TerritoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    code: str | None = Field(None, max_length=30)
    level: str | None = Field(None, pattern="^(region|zone|city|area)$")
    parent_id: uuid.UUID | None = None
    manager_user_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)
    status: str | None = Field(None, pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class TerritoryResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str | None = None
    level: str
    parent_id: str | None = None
    manager_user_id: str | None = None
    manager_name: str | None = None
    description: str | None = None
    status: str
    color: str | None = None
    branch_count: int
    pincode_count: int
    created_at: datetime


class TerritoryTreeNode(BaseModel):
    id: str
    name: str
    code: str | None = None
    level: str
    status: str
    manager_user_id: str | None = None
    children: list["TerritoryTreeNode"] = []


class LocationsResponse(BaseModel):
    regions: list[dict]
    zones: list[dict]
    cities: list[dict]
    areas: list[dict]


# ---------- Branch ----------
class BranchCreate(BaseModel):
    name: str = Field(..., max_length=150)
    code: str | None = Field(None, max_length=30)
    branch_manager_id: uuid.UUID | None = None
    territory_id: uuid.UUID | None = None
    address_line: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    pin_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    is_head_office: bool = False
    status: str = Field("active", pattern="^(active|archived)$")


class BranchUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    code: str | None = Field(None, max_length=30)
    branch_manager_id: uuid.UUID | None = None
    territory_id: uuid.UUID | None = None
    address_line: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    pin_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    is_head_office: bool | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")


class BranchResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str | None = None
    branch_manager_id: str | None = None
    manager_name: str | None = None
    territory_id: str | None = None
    territory_name: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    pin_code: str | None = None
    phone: str | None = None
    email: str | None = None
    is_head_office: bool
    status: str
    lead_count: int
    created_at: datetime


class BranchList(BaseModel):
    items: list[BranchResponse]
    total: int


# ---------- PIN mapping ----------
class PincodeUpsert(BaseModel):
    pin_code: str = Field(..., max_length=20)
    city: str | None = Field(None, max_length=100)
    territory_id: uuid.UUID
    branch_id: uuid.UUID | None = None


class PincodeResponse(BaseModel):
    id: str
    pin_code: str
    city: str | None = None
    territory_id: str
    territory_name: str | None = None
    branch_id: str | None = None
    branch_name: str | None = None


class PincodeList(BaseModel):
    items: list[PincodeResponse]
    total: int


# ---------- Lead assignment ----------
class LeadAssignRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(..., min_length=1)
    branch_id: uuid.UUID | None = None
    territory_id: uuid.UUID | None = None
    auto: bool = False


class LeadAssignResult(BaseModel):
    assigned: int
    unresolved: int


# ---------- Dashboards / performance ----------
class BranchDashboardResponse(BaseModel):
    total_branches: int
    active_branches: int
    archived_branches: int
    total_territories: int
    mapped_pincodes: int
    unmapped_leads: int
    top_branches: list[dict]


class BranchPerformanceResponse(BaseModel):
    branch_id: str
    name: str
    metrics: dict[str, Any]
    by_status: list[dict]


class BranchAnalyticsRow(BaseModel):
    branch_id: str
    name: str
    city: str | None = None
    manager_name: str | None = None
    leads: int
    converted: int
    conversion_rate: float
    revenue: float
    activities: int


class TerritoryAnalyticsRow(BaseModel):
    territory_id: str
    name: str
    level: str
    leads: int
    converted: int
    conversion_rate: float
    revenue: float
    activities: int


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[dict]

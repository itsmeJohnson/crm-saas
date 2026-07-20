import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    base_role: str = "Employee"  # Employee|Manager|OrgAdmin (inheritance seed)


class RoleUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    status: str | None = Field(None, pattern="^(active|archived)$")


class RoleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None = None
    base_role: str
    is_system: bool
    status: str
    user_count: int
    created_at: datetime


class MatrixCell(BaseModel):
    actions: dict[str, bool] = {}
    scope: str | None = None  # own|team|department|all


class MatrixUpdate(BaseModel):
    matrix: dict[str, MatrixCell]


class FieldPermissionItem(BaseModel):
    resource: str = Field(..., max_length=50)
    field_name: str = Field(..., max_length=100)
    access: str = Field(..., pattern="^(read|write|hidden)$")


class FieldPermissionsUpdate(BaseModel):
    items: list[FieldPermissionItem]


class RoleDetailResponse(RoleResponse):
    matrix: dict[str, Any] = {}
    field_permissions: list[FieldPermissionItem] = []


class RoleAssignRequest(BaseModel):
    user_ids: list[uuid.UUID]


class RoleUserItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool


class EffectivePermissionsResponse(BaseModel):
    base_role: str
    custom_role: dict | None = None
    matrix: dict[str, Any]
    fields: dict[str, Any] = {}


class PermissionAuditRow(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    actor_name: str
    metadata: dict | None = None
    created_at: datetime

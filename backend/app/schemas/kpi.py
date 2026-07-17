import uuid
from pydantic import BaseModel, Field


class KPICreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    category: str | None = None
    metric: str = "manual"
    unit: str | None = None
    comparison: str | None = None
    target_value: float = 0
    warning_value: float | None = None
    critical_value: float | None = None
    manual_value: float | None = None
    window_days: int = Field(30, ge=1, le=365)
    is_active: bool = True
    notify: bool = True
    notify_roles: list[str] | None = None


class KPIUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    category: str | None = None
    metric: str | None = None
    unit: str | None = None
    comparison: str | None = None
    target_value: float | None = None
    warning_value: float | None = None
    critical_value: float | None = None
    manual_value: float | None = None
    window_days: int | None = Field(None, ge=1, le=365)
    is_active: bool | None = None
    notify: bool | None = None
    notify_roles: list[str] | None = None


class KPIResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    category: str
    metric: str
    unit: str
    comparison: str
    target_value: float | None = None
    warning_value: float | None = None
    critical_value: float | None = None
    manual_value: float | None = None
    window_days: int
    is_active: bool
    notify: bool
    notify_roles: list[str]
    created_at: str | None = None

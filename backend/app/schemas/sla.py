from pydantic import BaseModel, Field


class PriorityTier(BaseModel):
    level: str
    response_hours: float | None = None
    resolution_hours: float | None = None


class PolicyCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    entity_type: str = "lead"
    response_hours: float | None = None
    resolution_hours: float | None = None
    priority_field: str = "priority"
    priorities: list[PriorityTier] | None = None
    business_hours_only: bool = False
    skip_holidays: bool = False
    conditions: dict | None = None
    on_breach: str = "notify_manager"
    escalate_after_hours: float | None = None
    escalate_to_role: str | None = None
    is_active: bool = True


class PolicyUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    entity_type: str | None = None
    response_hours: float | None = None
    resolution_hours: float | None = None
    priority_field: str | None = None
    priorities: list[PriorityTier] | None = None
    business_hours_only: bool | None = None
    skip_holidays: bool | None = None
    conditions: dict | None = None
    on_breach: str | None = None
    escalate_after_hours: float | None = None
    escalate_to_role: str | None = None
    is_active: bool | None = None


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    entity_type: str
    metric: str
    conditions: dict | None = None
    on_breach: str
    is_active: bool
    breach_count: int
    priority_field: str
    priorities: list[dict] | None = None
    response_hours: float | None = None
    resolution_hours: float | None = None
    business_hours_only: bool
    skip_holidays: bool
    escalate_after_hours: float | None = None
    escalate_to_role: str | None = None
    created_at: str | None = None


class TrackerResponse(BaseModel):
    id: str
    policy_id: str
    entity_type: str
    entity_id: str
    priority_level: str | None = None
    status: str
    response_hours: float | None = None
    resolution_hours: float | None = None
    started_at: str | None = None
    response_due_at: str | None = None
    resolution_due_at: str | None = None
    first_response_at: str | None = None
    resolved_at: str | None = None
    response_breached: bool
    resolution_breached: bool
    breach_type: str | None = None
    escalated: bool
    paused_seconds: int


class BreachResponse(BaseModel):
    id: str
    policy_id: str
    entity_type: str
    entity_id: str
    metric: str
    hours_elapsed: float
    resolved: bool
    breached_at: str | None = None


class EnableRequest(BaseModel):
    enabled: bool


class PauseRequest(BaseModel):
    reason: str | None = None


class ScanResult(BaseModel):
    breaches: int


class SLAReport(BaseModel):
    policies: int
    active: int
    total_trackers: int
    met: int
    breached: int
    compliance_rate: float
    open_breaches: int
    by_status: dict
    avg_response_hours: float


class SLADashboard(BaseModel):
    policies: int
    active: int
    compliance_rate: float
    open_breaches: int
    at_risk: int
    running: int
    recent_breaches: list[dict]

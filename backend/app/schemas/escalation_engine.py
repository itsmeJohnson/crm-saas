from pydantic import BaseModel, Field


class EscalationLevel(BaseModel):
    after_hours: float
    escalate_to: str
    value: str | None = None
    notify: bool = True


class RuleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    entity_type: str = "lead"
    trigger_condition: str = "no_activity"
    conditions: dict | None = None
    levels: list[EscalationLevel] = []
    business_hours_only: bool = False
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    entity_type: str | None = None
    trigger_condition: str | None = None
    conditions: dict | None = None
    levels: list[EscalationLevel] | None = None
    business_hours_only: bool | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    entity_type: str
    trigger_condition: str
    conditions: dict | None = None
    levels: list[dict]
    business_hours_only: bool
    is_active: bool
    run_count: int
    escalation_count: int
    created_at: str | None = None


class EventResponse(BaseModel):
    id: str
    rule_id: str
    entity_type: str
    entity_id: str
    level: int
    escalate_to: str | None = None
    escalated_to_user_id: str | None = None
    reason: str | None = None
    hours_elapsed: float | None = None
    escalated_at: str | None = None


class EnableRequest(BaseModel):
    enabled: bool


class ScanResult(BaseModel):
    escalations: int


class EscalationReport(BaseModel):
    rules: int
    active: int
    escalations: int
    by_entity: dict
    by_level: dict


class EscalationDashboard(BaseModel):
    rules: int
    active: int
    escalations: int
    last_7_days: int
    by_entity: dict
    recent: list[dict]

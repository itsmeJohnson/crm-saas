import uuid
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class RuleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    category: str | None = Field(None, max_length=80)
    entity_type: str = "lead"
    definition: dict = {}
    actions: list[dict] | None = None
    priority: int = 100
    conflict_strategy: str = "highest_priority"
    is_active: bool = True
    is_template: bool = False


class RuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    category: str | None = Field(None, max_length=80)
    entity_type: str | None = None
    definition: dict | None = None
    actions: list[dict] | None = None
    priority: int | None = None
    conflict_strategy: str | None = None
    is_active: bool | None = None
    is_template: bool | None = None


class RuleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None = None
    category: str | None = None
    entity_type: str
    definition: dict
    actions: list[dict] = []
    priority: int
    conflict_strategy: str
    is_active: bool
    is_template: bool
    condition_count: int
    action_count: int = 0
    match_count: int
    eval_count: int
    last_evaluated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PriorityRequest(BaseModel):
    priority: int


class TestRequest(BaseModel):
    # test against an explicit fact sample, or a real entity by id
    sample: dict | None = None
    entity_id: uuid.UUID | None = None


class TestResult(BaseModel):
    rule_id: str
    name: str
    matched: bool
    trace: dict
    facts: dict


class ResolveRequest(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    strategy: str | None = None


class ImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    format_: str | None = Field(None, alias="_format")
    name: str | None = None
    description: str | None = None
    category: str | None = None
    entity_type: str | None = None
    definition: dict | None = None
    priority: int | None = None
    conflict_strategy: str | None = None


class EvaluationRow(BaseModel):
    id: str
    rule_id: str
    entity_type: str
    entity_id: str | None = None
    matched: bool
    is_test: bool
    created_at: str | None = None


class RuleReport(BaseModel):
    total: int
    active: int
    inactive: int
    templates: int
    evaluations: int
    matches: int
    match_rate: float
    by_entity: dict


class RuleDashboard(BaseModel):
    total: int
    active: int
    match_rate: float
    evaluations: int
    top: list[dict]


class SimpleResult(BaseModel):
    created: int = 0


# ---------- Business Rule Designer ----------
class ComponentCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    entity_type: str = "lead"
    definition: dict = {}
    is_active: bool = True


class ComponentUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    entity_type: str | None = None
    definition: dict | None = None
    is_active: bool | None = None


class ComponentResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    entity_type: str
    definition: dict
    is_active: bool
    created_at: str | None = None


class VariableCreate(BaseModel):
    name: str = Field(..., max_length=80)
    description: str | None = None
    value_type: str = "string"
    value: Any | None = None


class VariableUpdate(BaseModel):
    description: str | None = None
    value_type: str | None = None
    value: Any | None = None


class VariableResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    value_type: str
    value: str | None = None
    resolved: Any | None = None
    created_at: str | None = None


class VersionRow(BaseModel):
    id: str
    version_no: int
    note: str | None = None
    snapshot: dict
    created_at: str | None = None


class RestoreRequest(BaseModel):
    version_no: int


class SimulateRequest(BaseModel):
    limit: int = Field(50, ge=1, le=200)
    execute: bool = False


class SimulateResult(BaseModel):
    rule_id: str
    name: str
    entity_type: str
    evaluated: int
    matched: int
    executed: int
    action_count: int
    samples: list[dict]


class AuditRow(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    actor_name: str | None = None
    metadata: dict | None = None
    created_at: str | None = None

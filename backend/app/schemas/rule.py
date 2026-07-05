import uuid
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class RuleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    category: str | None = Field(None, max_length=80)
    entity_type: str = "lead"
    definition: dict = {}
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
    priority: int
    conflict_strategy: str
    is_active: bool
    is_template: bool
    condition_count: int
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

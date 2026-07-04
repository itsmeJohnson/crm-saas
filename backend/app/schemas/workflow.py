import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkflowCondition(BaseModel):
    field: str
    op: str
    value: Any = None


class WorkflowAction(BaseModel):
    type: str
    # optional params depending on action type
    value: Any = None
    user_id: str | None = None
    stage_id: str | None = None
    content: str | None = None
    message: str | None = None
    subject: str | None = None       # send_email
    campaign_id: str | None = None   # add_to_campaign
    team_id: str | None = None       # assign_to_team
    territory_id: str | None = None  # assign_territory
    branch_id: str | None = None     # assign_territory


class WorkflowRuleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    trigger_event: str
    is_active: bool = True
    conditions: list[WorkflowCondition] = []
    actions: list[WorkflowAction] = []


class WorkflowRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    trigger_event: str | None = None
    is_active: bool | None = None
    conditions: list[WorkflowCondition] | None = None
    actions: list[WorkflowAction] | None = None


class WorkflowRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    trigger_event: str
    is_active: bool
    conditions: list[dict]
    actions: list[dict]
    created_at: datetime
    updated_at: datetime

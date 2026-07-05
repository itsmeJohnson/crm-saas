import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    type: str  # trigger|action|branch|merge|delay|loop|approval|end
    config: dict[str, Any] = {}


class GraphEdge(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    branch: str | None = None

    model_config = {"populate_by_name": True}


class WorkflowGraph(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []


class WorkflowCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=60)
    trigger_event: str
    graph: WorkflowGraph | None = None
    is_enabled: bool = True
    is_template: bool = False


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=60)
    trigger_event: str | None = None
    graph: WorkflowGraph | None = None
    is_enabled: bool | None = None
    is_template: bool | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    category: str | None = None
    status: str
    version: int
    is_enabled: bool
    is_template: bool
    trigger_event: str
    entity_type: str
    node_count: int
    created_at: datetime


class WorkflowDetail(WorkflowResponse):
    graph: dict = {}


class PublishRequest(BaseModel):
    notes: str | None = Field(None, max_length=300)


class EnableRequest(BaseModel):
    enabled: bool


class VersionRow(BaseModel):
    id: str
    version: int
    trigger_event: str
    notes: str | None = None
    published_by_name: str | None = None
    published_at: str | None = None


class RollbackRequest(BaseModel):
    version: int


class ExecutionStepRow(BaseModel):
    seq: int
    node_id: str | None = None
    node_type: str
    action_type: str | None = None
    status: str
    detail: str | None = None


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str | None = None
    version: int
    trigger_event: str
    entity_type: str
    entity_id: str | None = None
    status: str
    is_test: bool
    rolled_back: bool
    steps_run: int
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    steps: list[ExecutionStepRow] | None = None


class ExecutionList(BaseModel):
    items: list[ExecutionResponse]
    total: int


class WorkflowReport(BaseModel):
    total_workflows: int
    published: int
    enabled: int
    total_runs: int
    completed: int
    failed: int
    success_rate: float
    top_workflows: list[dict]


class WorkflowDashboard(BaseModel):
    published: int
    enabled: int
    total_runs: int
    success_rate: float
    failed: int
    recent: list[dict]


class ImportRequest(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    trigger_event: str
    graph: dict = {}
    is_template: bool = False


class SimpleResult(BaseModel):
    created: int

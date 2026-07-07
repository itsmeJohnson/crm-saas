from pydantic import BaseModel, Field, ConfigDict


# ---------- per-subsystem blocks ----------
class WorkflowBlock(BaseModel):
    total_runs: int
    completed: int
    failed: int
    paused: int
    success_rate: float
    failure_rate: float
    avg_execution_ms: float
    max_execution_ms: float


class QueueBlock(BaseModel):
    total: int
    succeeded: int
    failed: int
    dead_letter: int
    queued: int
    running: int
    success_rate: float
    avg_duration_ms: float


class JobsBlock(BaseModel):
    runs: int
    success: int
    failed: int
    partial: int
    success_rate: float
    items_processed: int
    avg_duration_ms: float
    enabled_jobs: int


class RulesBlock(BaseModel):
    total: int
    active: int
    evaluations: int
    matches: int
    match_rate: float


class SLABlock(BaseModel):
    tracked: int
    breached: int
    met: int
    open_breaches: int
    compliance_rate: float


class EscalationBlock(BaseModel):
    total: int
    by_level: dict
    by_entity: dict


class ApprovalBlock(BaseModel):
    total: int
    approved: int
    rejected: int
    pending: int
    cancelled: int
    approval_rate: float
    avg_decision_hours: float


# ---------- composite responses ----------
class OverviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    workflow: WorkflowBlock
    queue: QueueBlock
    automation_jobs: JobsBlock
    rules: RulesBlock
    sla: SLABlock
    escalation: EscalationBlock
    approval: ApprovalBlock


class TopWorkflow(BaseModel):
    workflow_id: str
    name: str
    runs: int
    failed: int


class WorkflowFailure(BaseModel):
    id: str
    workflow_id: str
    name: str
    trigger_event: str
    error: str | None = None
    started_at: str | None = None


class WorkflowsResponse(WorkflowBlock):
    top_workflows: list[TopWorkflow]
    failures: list[WorkflowFailure]


class QueueResponse(QueueBlock):
    by_queue: list[dict]
    by_type: list[dict]


class TopRule(BaseModel):
    id: str
    name: str
    entity_type: str
    evaluations: int
    matches: int
    match_rate: float


class RuleUsageResponse(RulesBlock):
    top_rules: list[TopRule]


class TopAutomationsResponse(BaseModel):
    items: list[dict]


class SLAComplianceResponse(SLABlock):
    breaches_by_metric: dict
    breaches_by_entity: dict


class EscalationResponse(EscalationBlock):
    by_target: dict


class ApprovalResponse(ApprovalBlock):
    by_type: dict


class TrendResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    granularity: str
    from_: str = Field(alias="from")
    to: str
    series: list[dict]


class DashboardResponse(BaseModel):
    workflow_runs: int
    workflow_success_rate: float
    workflow_failed: int
    queue_failed: int
    sla_compliance_rate: float
    open_breaches: int
    escalations: int
    approvals_pending: int

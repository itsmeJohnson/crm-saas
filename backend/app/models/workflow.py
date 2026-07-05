import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

# Orchestration workflow engine (additive — the legacy WorkflowRule single-rule
# engine is untouched and keeps working). A Workflow is a versioned, multi-step
# graph with a lifecycle (draft → published), execution history and rollback.
WORKFLOW_STATUSES = ("draft", "published", "archived")
NODE_TYPES = ("trigger", "action", "branch", "merge", "delay", "loop", "approval", "end")


class Workflow(BaseModel):
    """A designed, versioned automation workflow. `graph` is the visual
    definition: {"nodes": [{id, type, config}], "edges": [{from, to, branch?}]}.
    Published workflows run when their trigger fires; drafts do not."""
    __tablename__ = "workflows"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", nullable=False, index=True)  # draft|published|archived
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="lead", nullable=False)
    graph: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # {nodes:[], edges:[]}
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class WorkflowVersion(BaseModel):
    """An immutable snapshot of a workflow's graph taken at publish. Enables
    rollback to any prior published version."""
    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(40), nullable=False)
    graph: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowExecution(BaseModel):
    """One run of a workflow (or a test/dry run) against a trigger entity."""
    __tablename__ = "workflow_executions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="completed", nullable=False, index=True)  # completed|failed|paused|test
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steps_run: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowExecutionStep(BaseModel):
    """A per-node execution log line. `reverse` captures how to undo a mutating
    action so the execution can be rolled back."""
    __tablename__ = "workflow_execution_steps"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="success", nullable=False)  # success|skipped|failed
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reverse: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {entity_type, entity_id, field, old_value}

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AutomationJob(BaseModel):
    """Per-organization registry entry for one background automation job.

    Bootstrapped from AutomationService.JOB_CATALOG — one row per (org, job_key).
    Gives each existing/new automation an enable switch, schedule, retry policy
    and health counters, and is the anchor for its execution-log runs.

    job_key ∈ lead_reminders|escalation|sla_scan|scheduled_reports|dunning|
             missed_call|sms_retry|email_sync|campaign|task_reminders
    """
    __tablename__ = "automation_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    job_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    schedule: Mapped[str] = mapped_column(String(30), default="daily", nullable=False)  # daily|hourly|manual
    max_retries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(12), nullable=True)  # success|failed|partial
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("uq_automation_job_org_key", "organization_id", "job_key", unique=True),
    )


class AutomationRun(BaseModel):
    """One execution of an automation job — the unified execution log powering
    failure handling, retry accounting, dashboard and reports."""
    __tablename__ = "automation_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    job_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="running", nullable=False, index=True)  # running|success|failed|partial
    triggered_by: Mapped[str] = mapped_column(String(20), default="schedule", nullable=False)  # schedule|manual|retry
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SLAPolicy(BaseModel):
    """A service-level target on an entity: e.g. 'first response within 4h' or
    'resolution within 48h', optionally scoped by a Rule-Engine condition tree,
    with an on-breach action.

    metric ∈ first_response | resolution
    on_breach ∈ notify_owner | notify_manager | escalate
    """
    __tablename__ = "sla_policies"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="lead", nullable=False)
    metric: Mapped[str] = mapped_column(String(30), default="first_response", nullable=False)
    threshold_hours: Mapped[float] = mapped_column(Float, default=24.0, nullable=False)
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Rule-Engine definition tree
    on_breach: Mapped[str] = mapped_column(String(30), default="notify_manager", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    breach_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class SLABreach(BaseModel):
    """A recorded SLA breach for an entity+policy — dedups repeat alerts and
    powers SLA compliance reporting."""
    __tablename__ = "sla_breaches"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sla_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(30), nullable=False)
    hours_elapsed: Mapped[float] = mapped_column(Float, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    breached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScheduledReport(BaseModel):
    """A recurring report that is generated and delivered automatically.

    report_type ∈ lead_summary | activity_summary | sla_compliance | automation_health
    frequency ∈ daily | weekly | monthly
    channel ∈ in_app | email
    recipients: list of user ids (strings)
    """
    __tablename__ = "scheduled_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), default="lead_summary", nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="weekly", nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    recipients: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

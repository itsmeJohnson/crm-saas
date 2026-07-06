import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Schedule(BaseModel):
    """A configurable, recurring scheduled task.

    Unlike the single hardcoded midnight loop, a Schedule can run on a cron
    expression or a structured recurrence (hourly/daily/weekly/monthly/interval)
    at a specific local time, timezone-aware, optionally gated to business hours
    and skipping holidays. When due it dispatches `task_type` (with `task_config`)
    to an existing subsystem.

    task_type ∈ run_automation_job | enqueue_queue_job | run_report |
                event_publish | webhook | noop
    schedule_kind ∈ cron | interval | hourly | daily | weekly | monthly
    """
    __tablename__ = "schedules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    task_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    schedule_kind: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    cron_expr: Mapped[str | None] = mapped_column(String(120), nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(5), nullable=True)   # "HH:MM"
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 0=Mon..6=Sun
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)     # 1..31
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_holidays: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skip_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_schedules_due", "is_active", "next_run_at"),
    )


class ScheduleRun(BaseModel):
    """Execution-history row for one firing of a schedule (or a skip)."""
    __tablename__ = "schedule_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="success", nullable=False, index=True)  # success|failed|skipped
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)  # holiday | outside_business_hours
    triggered_by: Mapped[str] = mapped_column(String(20), default="schedule", nullable=False)  # schedule | manual
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ReportSchedule(BaseModel):
    """A first-class delivery schedule for a user-built Report Builder report:
    frequency (daily…yearly), file formats (csv/xlsx/pdf), channels
    (notification/email/whatsapp) and recipients. Distinct from the Automation
    Engine's fixed-type scheduled_reports and from ReportDefinition's inline
    notification-only schedule — both stay untouched."""
    __tablename__ = "report_schedules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    frequency: Mapped[str] = mapped_column(String(12), default="weekly", nullable=False)  # daily|weekly|monthly|quarterly|yearly
    formats: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # subset of csv|xlsx|pdf
    channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # subset of notification|email|whatsapp
    recipients: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # user ids (strings)
    extra_emails: Mapped[list | None] = mapped_column(JSON, nullable=True)  # external email addresses
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)  # re-attempts on failed cycles
    fail_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # consecutive failures this cycle
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(12), nullable=True)  # success|partial|failed
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class ReportDeliveryLog(BaseModel):
    """History: one row per delivery attempt of a schedule — status, per-channel
    results, artifact sizes and errors. Powers the History tab and retries."""
    __tablename__ = "report_delivery_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("report_definitions.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False, index=True)  # success|partial|failed
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(12), default="schedule", nullable=False)  # schedule|manual|retry
    frequency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    formats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # per-channel/per-recipient outcomes + artifact sizes
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

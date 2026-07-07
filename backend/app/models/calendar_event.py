import uuid
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Text, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CalendarEvent(BaseModel):
    """A scheduled calendar event (meeting/appointment/etc) with start/end and optional recurrence."""
    __tablename__ = "calendar_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), default="Meeting", nullable=False, index=True)  # Meeting|Appointment|Call|Followup|Other
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Scheduled", nullable=False, index=True)  # Scheduled|Completed|Cancelled

    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    attendees: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{user_id?, name, email}]

    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)

    recurrence: Mapped[str] = mapped_column(String(20), default="none", nullable=False)  # none|daily|weekly|monthly
    recurrence_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class Holiday(BaseModel):
    __tablename__ = "holidays"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recurring_annual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # repeats every year (same month/day)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)


class WorkingHoursConfig(BaseModel):
    """Singleton per organization. `days` = {mon: {enabled, start, end}, ...}."""
    __tablename__ = "working_hours_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    days: Mapped[dict] = mapped_column(JSON, nullable=False)

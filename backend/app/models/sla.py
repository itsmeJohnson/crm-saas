import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SLATracker(BaseModel):
    """A live SLA clock attached to one entity under one policy.

    Tracks the response and resolution deadlines (business-hours aware),
    supports pause/resume, and records the outcome. One tracker per
    (policy, entity); the scan flips it to `breached` when a deadline passes.

    status ∈ running | paused | response_met | met | breached | cancelled
    breach_type ∈ response | resolution
    """
    __tablename__ = "sla_trackers"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sla_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    priority_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    paused_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    breach_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_sla_trackers_scan", "organization_id", "status"),
        Index("ix_sla_trackers_entity", "entity_type", "entity_id"),
    )


class SLAPause(BaseModel):
    """A pause interval on an SLA tracker (e.g. waiting on the customer)."""
    __tablename__ = "sla_pauses"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    tracker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sla_trackers.id", ondelete="CASCADE"), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    paused_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

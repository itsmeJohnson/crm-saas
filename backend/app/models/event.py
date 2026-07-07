import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Event(BaseModel):
    """A published domain event — the immutable record on the event bus.

    Producers publish events (lead.created, payment.received, custom.*) without
    knowing their consumers; subscribers are matched and delivered separately.
    This row is the event log + monitoring anchor.

    source ∈ trigger | custom | system
    status ∈ published (always; delivery status lives on EventDelivery)
    """
    __tablename__ = "events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="trigger", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="published", nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_events_org_type", "organization_id", "event_type"),
    )


class EventSubscription(BaseModel):
    """A subscriber registration: deliver events matching `event_pattern` to a
    handler. Built-in subscribers (workflow_engine) are code-registered; these
    rows are the user-configurable ones (webhooks, log sinks).

    event_pattern: exact ("lead.created"), prefix wildcard ("lead.*"), or "*".
    subscriber_type ∈ webhook | log
    config: {"url": "..."} for webhook.
    """
    __tablename__ = "event_subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    event_pattern: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subscriber_type: Mapped[str] = mapped_column(String(20), default="webhook", nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class EventDelivery(BaseModel):
    """One attempt-set to deliver an event to a single subscriber — the per-
    delivery execution log, retry accounting and dead-letter record.

    status ∈ success | failed | dead_letter
    """
    __tablename__ = "event_deliveries"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event_subscriptions.id", ondelete="CASCADE"), nullable=True, index=True)
    subscriber: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_dead_letter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

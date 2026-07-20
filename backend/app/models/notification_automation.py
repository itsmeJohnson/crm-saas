import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class NotificationRule(BaseModel):
    """A rule that automatically sends notifications when a domain event fires.

    Subscribes to the Event Bus: on a matching `trigger_event`, optional Rule-
    Engine `conditions` are evaluated against the entity, `recipients` are
    resolved (owner/manager/creator/role/user), the `template` (or inline
    title/body with {{var}}) is rendered, and each recipient is notified over
    `channels` — immediately, or batched into a digest.

    recipients: list of {"type": owner|manager|creator|role|user, "value": ...}
    channels:   subset of in_app|email|sms|whatsapp|push
    """
    __tablename__ = "notification_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)  # bus event type or "*"
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Rule-Engine definition tree
    recipients: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
    priority: Mapped[str] = mapped_column(String(12), default="normal", nullable=False)
    digest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notif_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_notif_rules_org_trigger", "organization_id", "trigger_event", "is_active"),
    )


class NotificationDelivery(BaseModel):
    """Per-channel delivery record for one notification — powers delivery
    tracking, retry and channel/status reporting.

    status ∈ sent | failed | retrying | pending
    """
    __tablename__ = "notification_deliveries"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notification_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(12), nullable=False, index=True)  # in_app|email|sms|whatsapp|push
    status: Mapped[str] = mapped_column(String(12), default="sent", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queue_job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationDigestItem(BaseModel):
    """A pending digest entry, accumulated until a scheduled flush composes one
    summary notification per user."""
    __tablename__ = "notification_digest_items"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notification_rules.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

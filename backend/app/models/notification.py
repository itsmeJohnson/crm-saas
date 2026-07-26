import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, DateTime, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Notification(BaseModel):
    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # lead, billing, support, system, …
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Notification Center extensions
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False, index=True)  # low|normal|high|urgent
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{label, url, style}]
    channels_sent: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["in_app","email","sms","whatsapp","push"]


class NotificationPreference(BaseModel):
    """Per-user, per-category channel opt-ins. Absent row ⇒ defaults (in-app only)."""
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_notif_pref_user_category"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    whatsapp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    push: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PushSubscription(BaseModel):
    """A browser Web-Push subscription for a user (endpoint + keys)."""
    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_push_sub_user_endpoint"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DeviceToken(BaseModel):
    """A native mobile push token for a user — FCM (Android) or APNS (iOS).
    Parallel to PushSubscription (which is browser Web-Push); the notification
    dispatcher fans out to both. Unique per (user, token) so re-registering the
    same device is idempotent."""
    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_device_token_user_token"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)  # fcm | apns
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active_token: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

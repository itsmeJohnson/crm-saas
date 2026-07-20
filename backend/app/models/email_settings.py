import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class EmailSettings(BaseModel):
    """Per-organization mailbox config (one row per org).

    provider='mock' (default) simulates SMTP/IMAP in dev without credentials, like
    the other messaging modules. auth_method selects SMTP password auth vs. OAuth
    (Google/Microsoft). tracking_base_url is the public origin used to build open/
    click tracking URLs embedded in outbound HTML.
    """
    __tablename__ = "email_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_email_settings_organization"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    auth_method: Mapped[str] = mapped_column(String(30), default="smtp", nullable=False)  # smtp|oauth_google|oauth_microsoft
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # SMTP (send)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # IMAP (fetch inbound)
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imap_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # OAuth (Gmail / Microsoft 365)
    oauth_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    oauth_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking + state
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tracking_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)  # mock|smtp
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

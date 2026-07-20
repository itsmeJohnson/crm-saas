import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class WhatsAppSettings(BaseModel):
    """Per-organization WhatsApp Business config (one row per org).

    provider='mock' (default) simulates sends in dev without credentials, like
    email_service/SmsSettings. provider='meta' uses the WhatsApp Cloud API.
    webhook_token secures the status/inbound POST callbacks; webhook_verify_token
    is echoed back on Meta's GET verification handshake.
    """
    __tablename__ = "whatsapp_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_whatsapp_settings_organization"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)  # mock|meta
    phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    webhook_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    webhook_verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_reply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WhatsAppConversation(BaseModel):
    """One conversation per counterparty phone. Holds the 24-hour customer-care
    window (window_expires_at = last_inbound_at + 24h) and the agent assignment."""
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (UniqueConstraint("organization_id", "phone", name="uq_whatsapp_conversation_org_phone"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open|closed
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WhatsAppQuickReply(BaseModel):
    """Canned reply an agent can insert into the composer."""
    __tablename__ = "whatsapp_quick_replies"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shortcut: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

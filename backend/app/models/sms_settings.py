import uuid
from sqlalchemy import String, ForeignKey, Boolean, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SmsSettings(BaseModel):
    """Per-organization SMS provider configuration (one row per org).

    `provider='mock'` (the default) simulates sends in dev without credentials,
    mirroring how email_service falls back to a mock when SMTP is unconfigured.
    `webhook_token` is the shared secret that inbound + delivery-status webhooks
    must present, since those callbacks are unauthenticated by the provider.
    """
    __tablename__ = "sms_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_sms_settings_organization"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)  # mock|twilio|bhash|bulksmsplans
    account_sid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # from-number / sender ID
    # BhashSMS route: 'ndnd' = transactional (reaches DND numbers), 'dnd' = promotional.
    # Ignored by Mock/Twilio; a promotional sender (e.g. BHASH) must use 'dnd'.
    sms_priority: Mapped[str] = mapped_column(String(8), default="ndnd", nullable=False)
    # BulkSMSPlans route class: 'Transactional' | 'Promotional' | 'OTP'. Ignored by
    # Mock/Twilio/Bhash. For BulkSMSPlans, account_sid=api_id and auth_token=api_password.
    sms_type: Mapped[str] = mapped_column(String(20), default="Transactional", nullable=False)
    # Optional DLT-registered template id (India TRAI compliance); passed on each send
    # when set. BulkSMSPlans (and other DLT gateways) accept it per-message.
    default_template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    webhook_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class OtpVerification(BaseModel):
    """A single phone-number OTP verification attempt.

    The SMS gateway (BulkSMSPlans) generates and holds the actual code; we only
    persist the vendor ``provider_message_id`` returned by the send call, the
    target number, lifecycle status, and attempt/expiry bookkeeping so any CRM
    feature (phone verification, step-up auth) can drive a send→verify flow
    without knowing the gateway. Org-scoped; optionally linked to a lead/contact.
    """
    __tablename__ = "otp_verifications"
    __table_args__ = (
        Index("ix_otp_verifications_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. lead_phone, login
    provider: Mapped[str] = mapped_column(String(30), default="bulksmsplans", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending|verified|failed|expired
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class LeadCaptureSource(BaseModel):
    """A tenant-scoped inbound lead-capture endpoint.

    One row per connected ad source / web form. External platforms (Meta Lead
    Ads, Google Ads lead forms, landing pages, Zapier/Make) POST leads to a
    public, token-addressed webhook; each captured payload is mapped to a Lead
    and attributed to `source_label`. Leads created this way are owned by
    `owner_user_id` (the webhook has no logged-in actor).
    """
    __tablename__ = "lead_capture_sources"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # generic | meta_lead_ads | google_ads | web_form | zapier
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="generic")
    # Public secret embedded in the webhook URL; identifies the source.
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # Optional shared secret for HMAC-SHA256 signature verification of payloads.
    secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Meta requires a verify token echoed during the GET subscription handshake.
    meta_verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Value written to Lead.source for attribution (e.g. "Instagram Ads").
    source_label: Mapped[str] = mapped_column(String(100), nullable=False, default="Web Lead")
    default_pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True)
    # Leads captured via this source are created & assigned as this user.
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Optional {incoming_key: lead_field} overrides on top of the built-in mapping.
    field_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    leads_captured: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class LeadCaptureEvent(BaseModel):
    """One inbound webhook delivery. Doubles as the idempotency ledger (a repeat
    of the same external_id is a no-op) and the source's inbound activity log."""
    __tablename__ = "lead_capture_events"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_lead_capture_event_external"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead_capture_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    # Platform-provided id (Meta leadgen_id, Google lead_id, etc.) for dedup.
    external_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    # created | duplicate | error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, DateTime, JSON, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CampaignSegment(BaseModel):
    """Reusable audience definition (a saved filter over leads or contacts)."""
    __tablename__ = "campaign_segments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="lead", nullable=False)  # lead|contact
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    cached_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class Campaign(BaseModel):
    """A bulk outreach on one channel to a resolved audience, with delivery /
    engagement / conversion tracking and ROI (revenue − sent×cost_per_message)."""
    __tablename__ = "campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # SMS|Email|WhatsApp|Call
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communication_templates.id"), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # draft|scheduled|running|paused|completed|cancelled
    audience_type: Mapped[str] = mapped_column(String(20), default="filter", nullable=False)  # filter|list|segment
    audience_definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaign_segments.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="lead", nullable=False)  # lead|contact
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    converted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_per_message: Mapped[float] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    revenue: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class CampaignRecipient(BaseModel):
    """One queued send within a campaign, tracking its per-recipient lifecycle."""
    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_recipient_lead"),
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_recipient_contact"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True)
    to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)  # phone or email
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    # pending|sent|delivered|failed|opened|clicked|converted|skipped
    activity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

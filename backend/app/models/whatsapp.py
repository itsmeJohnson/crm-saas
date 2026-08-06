import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, DateTime, UniqueConstraint, Table, Column, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, Base


# Association Table for Many-to-Many Relationship between Conversations and Labels/Tags
whatsapp_conversation_labels = Table(
    "whatsapp_conversation_labels",
    Base.metadata,
    Column("conversation_id", ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("label_id", ForeignKey("whatsapp_labels.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class WhatsAppSettings(BaseModel):
    """Per-organization WhatsApp Business config/credentials.

    Supports multiple phone numbers/accounts per organization by making the organization_id
    and phone_number_id a composite unique constraint. Sensitive values (access_token,
    webhook_secret_enc) are encrypted at-rest using AESGCM.
    """
    __tablename__ = "whatsapp_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone_number_id", name="uq_whatsapp_settings_org_phone"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)  # mock|meta|twilio|gupshup
    phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    business_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted access token
    sender_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    meta_app_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    webhook_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    webhook_verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    webhook_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted webhook signature validation key
    webhook_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_version: Mapped[str] = mapped_column(String(20), default="v19.0", nullable=False)
    default_country_code: Mapped[str] = mapped_column(String(10), default="1", nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_reply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[str] = mapped_column(String(24), default="disconnected", nullable=False)  # connected|disconnected|rate_limited|expired_token|maintenance
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_rating: Mapped[str | None] = mapped_column(String(30), nullable=True)  # GREEN|YELLOW|RED
    messaging_limit: Mapped[str | None] = mapped_column(String(50), nullable=True)  # TIER_1K|TIER_10K|etc
    display_name_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # APPROVED|PENDING|REJECTED
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    conversations: Mapped[list["WhatsAppConversation"]] = relationship("WhatsAppConversation", back_populates="settings")


class WhatsAppContact(BaseModel):
    """Temporary/Unknown WhatsApp contacts before they are promoted/converted to CRM Leads."""
    __tablename__ = "whatsapp_contacts"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone", name="uq_whatsapp_contact_org_phone"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    conversations: Mapped[list["WhatsAppConversation"]] = relationship("WhatsAppConversation", back_populates="whatsapp_contact")


class WhatsAppLabel(BaseModel):
    """Custom tags/labels to categorize WhatsApp conversations (e.g. VIP, Hot Lead)."""
    __tablename__ = "whatsapp_labels"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_whatsapp_label_org_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#10B981", nullable=False)  # Hex code or Tailwind class name


class WhatsAppConversation(BaseModel):
    """Conversation thread associated with a specific counterparty number."""
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone", "whatsapp_settings_id", name="uq_whatsapp_conversation_org_phone_settings"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    whatsapp_settings_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("whatsapp_settings.id", ondelete="CASCADE"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    whatsapp_contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_contacts.id", ondelete="SET NULL"), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open|pending|resolved|closed
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamps & receipts
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # SLA response time tracking
    sla_status: Mapped[str] = mapped_column(String(20), default="normal", nullable=False, index=True)  # normal|warning|breached
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    response_time_sum: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Sum in seconds
    response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Agent Compose/Lock Lease (locks replying to 1 agent at a time for 5 minutes)
    locked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    settings: Mapped[WhatsAppSettings] = relationship("WhatsAppSettings", back_populates="conversations")
    whatsapp_contact: Mapped[WhatsAppContact | None] = relationship("WhatsAppContact", back_populates="conversations", lazy="selectin")
    messages: Mapped[list["WhatsAppMessage"]] = relationship("WhatsAppMessage", back_populates="conversation", order_by="WhatsAppMessage.created_at.asc()")
    labels: Mapped[list[WhatsAppLabel]] = relationship("WhatsAppLabel", secondary=whatsapp_conversation_labels, lazy="selectin")


class WhatsAppMessage(BaseModel):
    """WhatsApp message sent or received. Integrates outbox & AI intent metrics."""
    __tablename__ = "whatsapp_messages"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # INBOUND|OUTBOUND
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)  # unique Meta message ID (can be null for unsent Outbox)
    wa_status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)  # queued|sent|delivered|read|failed
    media_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)  # text|image|video|document|audio|location|contacts|template|interactive
    template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)  # True = team note

    # Message receipt timeline
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # AI readiness columns
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_sentiment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ai_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    conversation: Mapped[WhatsAppConversation] = relationship("WhatsAppConversation", back_populates="messages")
    attachments: Mapped[list["WhatsAppAttachment"]] = relationship("WhatsAppAttachment", back_populates="message", cascade="all, delete-orphan", lazy="selectin")


class WhatsAppAttachment(BaseModel):
    """WhatsApp media/files attachment mapped to a specific WhatsAppMessage."""
    __tablename__ = "whatsapp_attachments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("whatsapp_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    media_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # provider's media ID
    media_url: Mapped[str] = mapped_column(String(500), nullable=False)  # original/CDN URL
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # image|video|audio|document
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # path in persistent storage

    message: Mapped[WhatsAppMessage] = relationship("WhatsAppMessage", back_populates="attachments")


class WhatsAppTemplate(BaseModel):
    """Meta-approved templates synced locally for out-of-window broadcasts and campaigns."""
    __tablename__ = "whatsapp_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "language", name="uq_whatsapp_template_org_name_lang"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    meta_template_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # MARKETING|UTILITY|AUTHENTICATION
    language: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # en_US, etc.
    status: Mapped[str] = mapped_column(String(20), default="APPROVED", nullable=False)  # APPROVED|PENDING|REJECTED
    
    # Structure definition for variables validation
    header_format: Mapped[str | None] = mapped_column(String(20), nullable=True)  # TEXT|IMAGE|VIDEO|DOCUMENT|LOCATION
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    buttons: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # JSON description of actions/buttons


class WhatsAppWebhookEvent(BaseModel):
    """Durable log of raw Meta webhook payloads for idempotency checks, auditing, and retries."""
    __tablename__ = "whatsapp_webhook_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)  # deduplication/idempotency key
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # messages|statuses|message_template_status
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending|processed|failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WhatsAppQuickReply(BaseModel):
    """Canned reply an agent can insert into the composer."""
    __tablename__ = "whatsapp_quick_replies"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shortcut: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

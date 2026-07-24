import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, Numeric, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AIApiKey(BaseModel):
    """A developer API key for the public AI API.

    The raw secret is shown exactly once at creation/rotation; only its SHA-256
    hash is stored. `key_prefix` is the human-readable head (crm_live_ab12…) used
    for display and support lookups. Follows the BIToken precedent: the key acts
    on behalf of `created_by`, so every downstream service keeps its normal
    org scoping and RBAC.
    """
    __tablename__ = "ai_api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(8), default="live", nullable=False)  # live|test
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [] = all default scopes
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    daily_quota: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    allowed_providers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [] = unrestricted
    allowed_models: Mapped[list] = mapped_column(JSON, default=list, nullable=False)     # [] = unrestricted
    allowed_ips: Mapped[list] = mapped_column(JSON, default=list, nullable=False)        # [] = any origin
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class AIApiRequest(BaseModel):
    """One row per public-API request. Doubles as the rate-limit / quota ledger
    (sliding minute window + UTC-day counter) and the developer analytics feed —
    durable and test-friendly, mirroring the ai_cache approach."""
    __tablename__ = "ai_api_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_api_keys.id", ondelete="CASCADE"),
                                                         nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(8), default="POST", nullable=False)
    api_version: Mapped[str] = mapped_column(String(8), default="v1", nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200, nullable=False, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        Index("ix_ai_api_requests_key_created", "api_key_id", "created_at"),
    )


class AIWebhook(BaseModel):
    """Developer webhook endpoint. Receives signed AI platform events
    (ai.generation.completed, ai.quota.exceeded, …). The secret signs every
    delivery with HMAC-SHA256 so receivers can verify authenticity."""
    __tablename__ = "ai_webhooks"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [] = all events
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class AIWebhookDelivery(BaseModel):
    """One delivery attempt-set for one event to one webhook, with exponential
    backoff retries and a dead-letter terminal state (Event Bus precedent)."""
    __tablename__ = "ai_webhook_deliveries"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_webhooks.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)  # pending|success|failed|dead_letter
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

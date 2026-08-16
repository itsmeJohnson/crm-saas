import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Integration(BaseModel):
    """One configured external connection for an organization.

    The Integration Hub is a REGISTRY + RUNTIME, not a reimplementation: the
    channels that already have first-class modules (payment gateways, SMS,
    WhatsApp, email, BI cloud storage, outbound event webhooks) are surfaced in
    the hub as `is_managed_elsewhere` mirror rows so there is one inventory and
    one health view — their credentials keep living in their own tables and are
    never duplicated here.

    Rows created THROUGH the hub (ERP, accounting, HRMS, e-commerce, marketing,
    social, CRM connectors, identity/SSO/LDAP, calendar, cloud storage, and
    generic API/webhook connectors) store their own credentials + config and are
    driven by the generic connector runtime.
    """
    __tablename__ = "integrations"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # catalog key
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), default="live", nullable=False)  # live|sandbox

    # Credentials are stored per-connection. `auth_type` mirrors the catalog entry
    # (api_key|basic|bearer|oauth2|ldap|saml|none) and decides which fields matter.
    auth_type: Mapped[str] = mapped_column(String(12), default="api_key", nullable=False)
    credentials: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # masked on read
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)       # base_url, field maps, scopes…

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Mirror of a module that owns its own credentials (sms/email/whatsapp/payment/storage/webhook).
    is_managed_elsewhere: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    managed_by: Mapped[str | None] = mapped_column(String(40), nullable=True)  # module key that owns it

    # ---- health monitoring ----
    status: Mapped[str] = mapped_column(String(12), default="unconfigured", nullable=False, index=True)
    # unconfigured|healthy|degraded|down|disabled
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---- retry + fallback ----
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_backoff_seconds: Mapped[int] = mapped_column(Integer, default=2, nullable=False)  # base, doubled per attempt
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    # When this connection fails all attempts, the runtime transparently retries
    # the whole call on this connection instead. Cycles are rejected on write.
    fallback_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True)

    # ---- inbound webhook connector ----
    inbound_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    inbound_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_integrations_org_category", "organization_id", "category"),
    )


class IntegrationLog(BaseModel):
    """Every outbound call, health check, sync and fallback hop — the audit and
    health-history spine of the hub."""
    __tablename__ = "integration_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"),
                                                      nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # health_check|call|sync|inbound
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="success", nullable=False, index=True)
    # success|failed|retrying|fallback
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # set when this log row is the result of falling back FROM another connection
    fallback_from_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    request_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # secrets already redacted
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_integration_logs_int_created", "integration_id", "created_at"),
    )


class IntegrationEvent(BaseModel):
    """A payload RECEIVED from an external system on an inbound webhook
    connector. Stored verbatim so it can be replayed, and optionally forwarded
    onto the internal Event Bus."""
    __tablename__ = "integration_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"),
                                                      nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), default="inbound", nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    forwarded_event_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

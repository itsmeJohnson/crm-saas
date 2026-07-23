import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, Numeric, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AISettings(BaseModel):
    """Org-singleton AI Platform settings: default model routing, rate limiting
    (requests/day), budget cap (USD/month) and response caching."""
    __tablename__ = "ai_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_ai_settings_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_provider: Mapped[str] = mapped_column(String(20), default="mock", nullable=False)
    default_model: Mapped[str] = mapped_column(String(80), default="mock-ai", nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    daily_request_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)  # rate limiting
    monthly_budget_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=100, nullable=False)  # cost cap
    cache_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cache_ttl_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    streaming_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memory_messages: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # conversation window
    context_max_chars: Mapped[int] = mapped_column(Integer, default=4000, nullable=False)  # context manager budget


class AIProviderConfig(BaseModel):
    """One configured LLM provider for an org. Multiple rows form the model
    selection + fallback chain (ordered by priority). Provider keys:
    mock|openai|azure_openai|anthropic|gemini|ollama|custom."""
    __tablename__ = "ai_provider_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(300), nullable=True)  # azure endpoint / ollama / custom
    deployment: Mapped[str | None] = mapped_column(String(120), nullable=True)  # azure deployment name
    api_version: Mapped[str | None] = mapped_column(String(40), nullable=True)  # azure api-version
    default_model: Mapped[str] = mapped_column(String(80), nullable=False)
    models: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{model, input_cost_per_1k, output_cost_per_1k}]
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # fallback order (1 = first)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class AIPromptTemplate(BaseModel):
    """Prompt Engine: reusable versioned prompt with {{variable}} placeholders,
    an optional system prompt and per-template model/temperature overrides.
    task_type ties templates to platform integrations (crm/report/communication/…)."""
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_ai_template_org_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), default="general", nullable=False, index=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)  # {{var}} placeholders
    model_override: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # seeded platform templates
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # ---- Prompt Studio authoring overlay (additive; defaults keep legacy behavior) ----
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False, index=True)  # draft|pending_review|approved|rejected|archived
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # detected {{var}} names
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIPromptTemplateVersion(BaseModel):
    """Immutable snapshot of a prompt template captured before each content edit
    (and on restore) — powers Prompt Versioning + Prompt History."""
    __tablename__ = "ai_prompt_template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version", name="uq_ai_prompt_version"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_prompt_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    model_override: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIConversation(BaseModel):
    """Conversation Memory: a persistent chat thread, optionally bound to a CRM
    record (context_type/context_id) so the Context Manager grounds every turn."""
    __tablename__ = "ai_conversations"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation", nullable=False)
    context_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # lead|contact|company|report
    context_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIMessage(BaseModel):
    __tablename__ = "ai_messages"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0, nullable=False)


class AIUsageLog(BaseModel):
    """AI Logging + Token Usage + Cost Tracking + Monitoring: one row per
    gateway call (including cache hits and failed fallback attempts)."""
    __tablename__ = "ai_usage_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), default="general", nullable=False, index=True)
    template_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="success", nullable=False, index=True)  # success|failed|cached
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_from: Mapped[str | None] = mapped_column(String(20), nullable=True)  # provider that failed first
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AICacheEntry(BaseModel):
    """Response cache: deterministic requests (same provider/model/messages)
    are served from here inside the TTL — durable and test-friendly."""
    __tablename__ = "ai_cache"
    __table_args__ = (UniqueConstraint("organization_id", "cache_key", name="uq_ai_cache_org_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # sha256
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

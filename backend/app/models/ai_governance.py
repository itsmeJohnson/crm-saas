import uuid
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AIGovernancePolicy(BaseModel):
    """Org-singleton AI security & governance policy. Every field defaults to
    the safe-but-non-breaking posture: PII is masked (not blocked), injection is
    blocked, content filtering is off until terms are configured, and no
    provider/model restrictions until an allowlist is set."""
    __tablename__ = "ai_governance_policies"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_ai_gov_policy_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # PII detection + masking
    pii_detection: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pii_action: Mapped[str] = mapped_column(String(10), default="mask", nullable=False)  # mask|block|flag
    pii_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [] = all detectors

    # Prompt-injection protection
    injection_protection: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    injection_action: Mapped[str] = mapped_column(String(10), default="block", nullable=False)  # block|flag

    # Content filtering
    content_filter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_terms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Model / provider restrictions ([] = unrestricted)
    allowed_providers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_models: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    role_restrictions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # {role: [task_type,...]}

    # Usage policy + hallucination safeguards
    max_prompt_chars: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    require_grounding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    log_prompt_snippets: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AIGovernanceEvent(BaseModel):
    """Compliance log: one row per governance decision on an AI request."""
    __tablename__ = "ai_governance_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # pii|injection|content|model_restriction|prompt_size|clean
    action_taken: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # allowed|masked|blocked|flagged
    rule: Mapped[str | None] = mapped_column(String(80), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    findings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    prompt_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)  # already redacted

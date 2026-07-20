import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class EscalationRule(BaseModel):
    """A configurable, multi-level escalation rule.

    When an entity meets `trigger_condition` for longer than a level's
    `after_hours`, the engine escalates it to that level's target (manager,
    department head, role, user, or the skip-level manager) — walking up the
    chain as time passes. Optional Rule-Engine `conditions` gate which entities
    the rule applies to.

    entity_type ∈ lead | task | call | ticket | approval
    trigger_condition ∈ no_activity | overdue | unresolved | unreturned_call | pending
    levels: [{"after_hours": float, "escalate_to": manager|department_head|role|user|
              skip_level_manager, "value": role/user id, "notify": bool}]
    """
    __tablename__ = "escalation_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="lead", nullable=False, index=True)
    trigger_condition: Mapped[str] = mapped_column(String(30), default="no_activity", nullable=False)
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Rule-Engine tree
    levels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_escalation_rules_org_active", "organization_id", "entity_type", "is_active"),
    )


class EscalationEvent(BaseModel):
    """A recorded escalation firing — dedups repeat escalations of the same
    entity to the same level, and powers the dashboard / reports / audit."""
    __tablename__ = "escalation_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escalation_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    escalate_to: Mapped[str | None] = mapped_column(String(30), nullable=True)
    escalated_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hours_elapsed: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

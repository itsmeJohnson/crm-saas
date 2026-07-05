import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Rule(BaseModel):
    """A reusable, named boolean rule: a nested condition tree ("definition")
    evaluated against an entity's fact map by the Rule Engine.

    Rules are referenced by the workflow engine (trigger/branch nodes may carry
    a `rule_id`) and can be tested, prioritised and resolved for conflicts. The
    `definition` is the tree grammar documented in services/rule_evaluator.py.

    entity_type: lead|contact|task|attendance|leave|approval|performance|user
    priority:    higher wins when resolving conflicts among matching rules
    conflict_strategy: highest_priority|first_match|all (how resolve() picks)
    """
    __tablename__ = "rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead", index=True)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    conflict_strategy: Mapped[str] = mapped_column(String(30), default="highest_priority", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # denormalised counters for cheap reporting
    match_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    eval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_rules_org_entity_active", "organization_id", "entity_type", "is_active"),
    )


class RuleEvaluation(BaseModel):
    """A single evaluation of a rule (live or via the tester) — powers the
    evaluation history + reports without touching entity hot paths."""
    __tablename__ = "rule_evaluations"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trace: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

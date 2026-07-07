"""Business Rule Designer — additive tables layered on the Rule Engine.

These extend the reusable `Rule` (see app/models/rule.py) into a full designer:
- `RuleComponent`  — a named, reusable condition-tree fragment referenced inside
                     rule/other-component definitions via a `{"type":"ref","ref_id":...}`
                     node (expanded server-side before validation/evaluation).
- `RuleVariable`   — an org-defined named constant usable in expressions via
                     value_type="variable" (alongside the built-in dynamic vars).
- `RuleVersion`    — an immutable snapshot of a rule taken on every change, for
                     version history and one-click rollback.

The rule ACTIONS themselves live on the existing `rules` table (new nullable
`actions` JSON column added by the same migration) so a rule stays a single row.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class RuleComponent(BaseModel):
    """A reusable, named condition-tree fragment. Its `definition` is the same
    group/condition grammar as a rule and is substituted wherever a rule (or
    another component) references it by id."""
    __tablename__ = "rule_components"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead", index=True)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class RuleVariable(BaseModel):
    """An org-defined named constant (e.g. HIGH_VALUE_THRESHOLD = 50000) usable
    in rule expressions via value_type='variable'. `value` is stored as text and
    coerced by `value_type` at resolve time."""
    __tablename__ = "rule_variables"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)  # unique per org (enforced in service)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)  # string|number|bool|date
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_rule_variables_org_name", "organization_id", "name"),
    )


class RuleVersion(BaseModel):
    """An immutable snapshot of a rule's editable fields at a point in time —
    powers version history and rollback."""
    __tablename__ = "rule_versions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)  # name/description/definition/actions/priority/...
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

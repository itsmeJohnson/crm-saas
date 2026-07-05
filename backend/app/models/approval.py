import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Boolean, Integer, Numeric, Date, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

# Approval request types the generic engine understands. Leave/attendance/
# template have their own rich flows too — this engine is the org-wide,
# multi-level, delegatable approval surface for everything else (and can also
# carry a leave request generically).
APPROVAL_TYPES = ("leave", "expense", "discount", "quotation", "target", "user", "role", "generic")


class ApprovalChain(BaseModel):
    """A configurable multi-level approval chain for a request type. `steps` is
    an ordered JSON list [{level, approver_role, approver_user_id}]. `min_amount`
    lets a type have tiered chains (e.g. discount > 5000 needs a 2-level chain);
    the engine picks the active chain for the type with the highest min_amount
    that is <= the request amount."""
    __tablename__ = "approval_chains"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # one of APPROVAL_TYPES
    min_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False)  # [{level, approver_role, approver_user_id}]
    escalation_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # auto-escalate if pending longer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class ApprovalRequest(BaseModel):
    """A single approval request moving through a chain's levels."""
    __tablename__ = "approval_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. 'quotation','user'
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chain_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approval_chains.id"), nullable=True, index=True)
    current_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_levels: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False, index=True)  # pending|approved|rejected|cancelled
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class ApprovalAction(BaseModel):
    """One recorded action against a request — the approval history trail."""
    __tablename__ = "approval_actions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    on_behalf_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # set when a delegate acts
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approved|rejected|escalated|delegated|cancelled|submitted
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ApprovalDelegation(BaseModel):
    """A delegator hands their approval authority to a delegate for a date range
    (and optionally a single request_type)."""
    __tablename__ = "approval_delegations"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    delegator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    delegate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # null = all types
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

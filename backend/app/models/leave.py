import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Boolean, Integer, Numeric, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class LeaveType(BaseModel):
    """An org-defined category of leave (Casual, Sick, Earned, Unpaid, …).
    `annual_quota` is the default yearly allocation; `deducts_balance` lets an
    unpaid/optional type skip quota accounting. Holiday Calendar is NOT modelled
    here — it reuses the existing `holidays` table (calendar module)."""
    __tablename__ = "leave_types"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_leave_type_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    annual_quota: Mapped[float] = mapped_column(Numeric(5, 1), default=0, nullable=False)
    max_consecutive_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_half_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deducts_balance: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class LeaveBalance(BaseModel):
    """A user's yearly allocation for a leave type. `used`/`pending` are derived
    from requests at read time; only allocation + carry-forward are stored."""
    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "leave_type_id", "year",
                                       name="uq_leave_balance_user_type_year"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    allocated: Mapped[float] = mapped_column(Numeric(6, 1), default=0, nullable=False)
    carried_forward: Mapped[float] = mapped_column(Numeric(6, 1), default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class LeaveRequest(BaseModel):
    """A leave or work-from-home request. `request_type='wfh'` needs no leave
    type and never deducts balance. `day_count` is the number of working days
    (weekends + holidays excluded), with 0.5 for a half day."""
    __tablename__ = "leave_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(10), default="leave", nullable=False, index=True)  # leave|wfh
    leave_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leave_types.id"), nullable=True, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    half_day_period: Mapped[str | None] = mapped_column(String(12), nullable=True)  # first_half|second_half
    day_count: Mapped[float] = mapped_column(Numeric(5, 1), default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False, index=True)  # pending|approved|rejected|cancelled
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

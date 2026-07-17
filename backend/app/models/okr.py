import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Objective(BaseModel):
    """A Goal/OKR objective at company, department, team or individual level for
    a quarterly/annual/custom cycle. Progress is the weighted average of its key
    results (computed at read time — metric-linked KRs pull live rollups, manual
    KRs use their checked-in current_value). Distinct from PerformanceGoal /
    TeamTarget / DepartmentTarget, which stay the single-metric target stores."""
    __tablename__ = "objectives"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # company|department|team|individual
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)  # accountable person
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True, index=True)  # alignment
    cycle_type: Mapped[str] = mapped_column(String(12), default="quarterly", nullable=False)  # quarterly|annual|custom
    cycle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-4 when quarterly
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False, index=True)  # draft|active|completed|cancelled
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class KeyResult(BaseModel):
    """A measurable key result under an objective. kind=metric reads a live
    rollup (leads_converted/calls_made/tasks_completed/revenue/activities) for
    the objective's scope; kind=manual is updated through check-ins."""
    __tablename__ = "key_results"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    objective_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), default="manual", nullable=False)  # manual|metric
    metric: Mapped[str | None] = mapped_column(String(40), nullable=True)  # OKR_METRICS key when kind=metric
    unit: Mapped[str] = mapped_column(String(12), default="count", nullable=False)  # count|percent|currency
    start_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)  # active|completed
    last_checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class OKRReview(BaseModel):
    """A check-in, periodic review, or manager feedback entry on an objective.
    Check-ins are written automatically when a KR value is updated; reviews and
    feedback are explicit entries (feedback is manager/admin-only)."""
    __tablename__ = "okr_reviews"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    objective_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    key_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("key_results.id", ondelete="SET NULL"), nullable=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(12), default="checkin", nullable=False, index=True)  # checkin|review|feedback
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5 (reviews/feedback)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100 (check-ins)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    progress_at: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)  # objective progress when written

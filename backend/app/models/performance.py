import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

# Computable metrics a KPI/goal can track (all derived at read time from existing
# data — leads, activities, tasks, customer payments, attendance records).
PERFORMANCE_METRICS = (
    "calls_made", "leads_converted", "conversion_rate", "sales_revenue",
    "recovery_amount", "tasks_completed", "activities", "attendance_score",
)


class PerformanceKPI(BaseModel):
    """An org-defined KPI: names a computable metric, its display unit, whether
    higher is better, and a weight used when combining KPIs into a composite
    performance score. Distinct from the legacy org-level PerformanceTarget and
    from department/team targets — this drives the per-user scorecard."""
    __tablename__ = "performance_kpis"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_perf_kpi_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metric: Mapped[str] = mapped_column(String(30), nullable=False)  # one of PERFORMANCE_METRICS
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unit: Mapped[str] = mapped_column(String(12), default="count", nullable=False)  # count|percent|currency
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)  # composite-score weight
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class PerformanceGoal(BaseModel):
    """A per-user target for a KPI over a period. `achieved`/`attainment` are
    derived at read time from the KPI's metric between start_date and end_date."""
    __tablename__ = "performance_goals"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kpi_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("performance_kpis.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(12), default="monthly", nullable=False)  # daily|weekly|monthly|quarterly|yearly
    target_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False, index=True)  # active|archived
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class PerformanceAchievement(BaseModel):
    """A recorded achievement, created when a goal is evaluated as met. Idempotent
    per (goal, user) via a unique key so re-evaluation doesn't duplicate."""
    __tablename__ = "performance_achievements"
    __table_args__ = (UniqueConstraint("goal_id", "user_id", name="uq_perf_achievement_goal_user"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("performance_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    kpi_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("performance_kpis.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    badge: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Bronze|Silver|Gold
    period_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    achieved_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    attainment: Mapped[float] = mapped_column(Numeric(6, 1), default=0, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

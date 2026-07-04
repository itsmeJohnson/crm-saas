import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Numeric, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Department(BaseModel):
    """An org unit that groups users orthogonally to the reporting hierarchy.

    Reuses the existing User architecture: members are Users carrying
    `department_id`, and the head is a User. Supports a self-referential parent
    hierarchy, budget, status, and department-level targets/KPIs.
    """
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_department_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    budget: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    budget_period: Mapped[str | None] = mapped_column(String(20), nullable=True)  # monthly|quarterly|yearly
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class DepartmentTarget(BaseModel):
    """A department-level goal for a metric over a period (distinct from the
    org-level PerformanceTarget, which is left untouched)."""
    __tablename__ = "department_targets"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)  # leads_converted|calls_made|tasks_completed|revenue|activities|custom
    target_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class EmployeeTraining(BaseModel):
    """A training / certification record for an employee. Powers the Employee
    Analytics 'Training Score' — the only genuinely-missing data source (all other
    employee metrics come from existing leads/activities/tasks/attendance/leave)."""
    __tablename__ = "employee_trainings"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="completed", nullable=False, index=True)  # planned|in_progress|completed
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_employee_trainings_org_user", "organization_id", "user_id"),
    )

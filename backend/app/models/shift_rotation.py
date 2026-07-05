import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Integer, Date, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ShiftRotation(BaseModel):
    """A rotating shift pattern: users cycle through `shift_sequence` (an ordered
    list of shift ids), advancing every `rotation_days` days. Complements the
    fixed date-ranged ShiftAssignment — a user on a rotation has their shift for
    a given date computed from their anchor date rather than stored per day."""
    __tablename__ = "shift_rotations"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_shift_rotation_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    shift_sequence: Mapped[list] = mapped_column(JSON, nullable=False)  # ordered list of shift id strings
    rotation_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)  # days per shift before rotating
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class ShiftRotationMember(BaseModel):
    """Assigns a user to a rotation from `anchor_date` (the cycle's day 0).
    `end_date` null = ongoing."""
    __tablename__ = "shift_rotation_members"
    __table_args__ = (UniqueConstraint("rotation_id", "user_id", name="uq_shift_rotation_member"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    rotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shift_rotations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

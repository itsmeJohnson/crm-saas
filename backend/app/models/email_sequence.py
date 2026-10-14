import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, Boolean, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class EmailSequence(BaseModel):
    """A multi-step, time-delayed auto-email follow-up (a drip). Steps carry
    editable subject/body templates with {{placeholders}}; enrollments walk a
    lead through the steps on a schedule."""

    __tablename__ = "email_sequences"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "manual"  → enrolled explicitly; "lead_created" → auto-enroll new leads.
    trigger: Mapped[str] = mapped_column(String(30), default="manual", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    steps: Mapped[list["EmailSequenceStep"]] = relationship(
        "EmailSequenceStep", back_populates="sequence",
        order_by="EmailSequenceStep.step_order", cascade="all, delete-orphan")


class EmailSequenceStep(BaseModel):
    __tablename__ = "email_sequence_steps"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    sequence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-based
    delay_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # wait from prior step (step 0 = from enrollment)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sequence: Mapped["EmailSequence"] = relationship("EmailSequence", back_populates="steps")


class SequenceEnrollment(BaseModel):
    """One lead's progress through one sequence. ``current_step`` is the index of
    the next step to send; ``next_run_at`` is when that step is due."""

    __tablename__ = "sequence_enrollments"
    __table_args__ = (UniqueConstraint("sequence_id", "lead_id", name="uq_enrollment_sequence_lead"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    sequence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|completed|cancelled
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrolled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

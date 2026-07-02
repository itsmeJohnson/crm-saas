import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Task(BaseModel):
    """A dedicated task (distinct from the generic Activity model).

    Optionally linked to a lead/contact/company. Backward-compatible: existing
    Activity(activity_type='Task') rows are unaffected.
    """
    __tablename__ = "tasks"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Medium", nullable=False, index=True)  # Low|Medium|High|Urgent
    status: Mapped[str] = mapped_column(String(20), default="Todo", nullable=False, index=True)  # Todo|InProgress|Done|Cancelled
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Optional record links
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Recurrence
    recurrence: Mapped[str] = mapped_column(String(20), default="none", nullable=False)  # none|daily|weekly|monthly
    recurrence_parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)

    checklist: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{id, text, done}]
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{filename, url, size, uploaded_by, uploaded_at}]

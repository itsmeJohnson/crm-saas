import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, Boolean, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CommunicationTemplate(BaseModel):
    """Reusable message template for the Communication Center (Email/SMS/WhatsApp/Call script).

    Extended with categories, an approval workflow (draft→pending_approval→
    approved/rejected), version tracking, and usage counters. `status` defaults
    to 'approved' so the legacy quick-create path stays immediately usable.
    """
    __tablename__ = "communication_templates"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="Email", nullable=False, index=True)  # Email|SMS|WhatsApp|Call
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # supports {{first_name}}, {{company}}, {{owner}} placeholders
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Categorisation + approval workflow
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False, index=True)  # draft|pending_approval|approved|rejected
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CommunicationTemplateVersion(BaseModel):
    """Immutable snapshot of a template at a point in time (one row per edit)."""
    __tablename__ = "communication_template_versions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("communication_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class CommunicationFlag(BaseModel):
    """Per-user read / pinned state on a communication (an Activity row)."""
    __tablename__ = "communication_flags"
    __table_args__ = (UniqueConstraint("user_id", "activity_id", name="uq_comm_flag_user_activity"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

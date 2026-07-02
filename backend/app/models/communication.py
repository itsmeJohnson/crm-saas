import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CommunicationTemplate(BaseModel):
    """Reusable message template for the Communication Center (email/SMS/WhatsApp)."""
    __tablename__ = "communication_templates"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="Email", nullable=False, index=True)  # Email|SMS|WhatsApp
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # supports {{first_name}}, {{company}}, {{owner}} placeholders
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)


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

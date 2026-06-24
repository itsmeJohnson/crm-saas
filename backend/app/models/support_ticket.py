import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class SupportTicket(BaseModel):
    __tablename__ = "support_tickets"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    ticket_number: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        index=True, 
        nullable=False, 
        default=lambda: f"TCK-{uuid.uuid4().hex[:8].upper()}"
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="Medium", nullable=False)  # "Low", "Medium", "High", "Critical"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # list of URLs/paths
    status: Mapped[str] = mapped_column(String(50), default="Open", nullable=False)  # "Open", "In_Progress", "Resolved", "Closed"
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)  # list of {"author": str, "content": str, "timestamp": str}
    history: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)  # list of {"status": str, "by": str, "timestamp": str}

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    assigned_to: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to_id])

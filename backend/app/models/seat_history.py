import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class SeatAssignmentHistory(BaseModel):
    __tablename__ = "seat_assignment_history"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "Assigned", "Inactive", "Released"
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships using string references to avoid circular dependency
    user = relationship("User", foreign_keys=[user_id])
    performed_by = relationship("User", foreign_keys=[performed_by_id])

    @property
    def user_name(self) -> str | None:
        if self.user:
            return f"{self.user.first_name or ''} {self.user.last_name or ''}".strip() or self.user.email
        return None

    @property
    def performed_by_name(self) -> str | None:
        if self.performed_by:
            return f"{self.performed_by.first_name or ''} {self.performed_by.last_name or ''}".strip() or self.performed_by.email
        return None

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Boolean, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class AssignmentStrategy(str, enum.Enum):
    ROUND_ROBIN = "ROUND_ROBIN"
    MANUAL = "MANUAL"

class AssignmentConfig(Base):
    __tablename__ = "assignment_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assignment_strategy: Mapped[AssignmentStrategy] = mapped_column(Enum(AssignmentStrategy, native_enum=False), default=AssignmentStrategy.ROUND_ROBIN, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    last_assigned_user: Mapped["User"] = relationship("User")

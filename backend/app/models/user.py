import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="Employee")  # SuperAdmin, OrgAdmin, Manager, Employee
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(default=1, nullable=False)
    is_invited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reporting_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    
    # Password Reset
    reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_token_expires: Mapped[datetime | None] = mapped_column(nullable=True)


    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    reporting_to: Mapped["User | None"] = relationship("User", remote_side="User.id", back_populates="downlines")
    downlines: Mapped[list["User"]] = relationship("User", back_populates="reporting_to")
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )

from datetime import datetime
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Subscription management
    subscription_plan: Mapped[str] = mapped_column(String(50), default="Trial")
    subscription_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(50), default="active")
    max_users: Mapped[int] = mapped_column(default=50)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", 
        back_populates="organization", 
        cascade="all, delete-orphan"
    )
    subscription: Mapped["TenantSubscription | None"] = relationship(
        "TenantSubscription", 
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan"
    )


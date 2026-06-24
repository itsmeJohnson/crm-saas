import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, DateTime, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class TenantSubscription(BaseModel):
    __tablename__ = "tenant_subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True, 
        index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # trial, active, expiring_soon, expired, suspended
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Support cycle metrics & commercial constraints
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)  # "monthly", "quarterly", "annual"
    next_invoice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    users_purchased: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    users_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    storage_used: Mapped[float] = mapped_column(Numeric(10, 3), default=0.0, nullable=False)  # in GB
    call_recording_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # count or minutes

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="subscription")
    plan: Mapped["Plan"] = relationship("Plan")


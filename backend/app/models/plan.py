from datetime import datetime
from sqlalchemy import String, Numeric, Integer, Boolean, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class Plan(BaseModel):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    price_inr: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    billing_cycle_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_admins: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_managers: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_team_leads: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_employees: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Commercial Enterprise Extensions
    display_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    quarterly_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    annual_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    recording_retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    priority_support: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    setup_charges: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    minimum_users: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    maximum_users: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    minimum_contract_months: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    promo_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    promo_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promo_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    plan_features: Mapped[list["PlanFeature"]] = relationship(
        "PlanFeature", 
        back_populates="plan", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )


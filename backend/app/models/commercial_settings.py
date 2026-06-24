from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class CommercialSettings(Base):
    __tablename__ = "commercial_settings"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default="default")
    
    # General Settings
    default_currency: Mapped[str] = mapped_column(String(10), default="INR")
    currency_symbol: Mapped[str] = mapped_column(String(10), default="₹")
    default_timezone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata")
    
    # Tax Settings
    default_gst: Mapped[float] = mapped_column(Numeric(5, 2), default=18.0)
    gst_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_label: Mapped[str] = mapped_column(String(50), default="GST")
    
    # Trial Settings
    default_trial_days: Mapped[int] = mapped_column(Integer, default=14)
    allow_trial: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_reminder_days: Mapped[int] = mapped_column(Integer, default=3)
    
    # Contract Settings
    default_min_contract: Mapped[int] = mapped_column(Integer, default=3)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=True)
    notice_period_days: Mapped[int] = mapped_column(Integer, default=15)
    
    # Setup Charges
    default_setup_charge: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    allow_setup_discount: Mapped[bool] = mapped_column(Boolean, default=True)
    free_setup_on_annual: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # User Pricing
    default_extra_user_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    minimum_users: Mapped[int] = mapped_column(Integer, default=10)
    maximum_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Discount Settings
    default_discount_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    maximum_discount_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=25.0)
    allow_custom_discount: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_promo_code: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Late Payment Settings
    late_payment_charge: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    late_payment_type: Mapped[str] = mapped_column(String(20), default="flat")
    grace_period_days: Mapped[int] = mapped_column(Integer, default=7)
    auto_suspend_days: Mapped[int] = mapped_column(Integer, default=30)
    auto_reactivate: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Reminder Settings (comma-separated days)
    reminder_schedule: Mapped[str] = mapped_column(String(500), default="{}")
    invoice_reminder_days: Mapped[str] = mapped_column(String(50), default="7,3,1")
    subscription_reminder_days: Mapped[str] = mapped_column(String(50), default="15,7,3,0")
    payment_reminder_days: Mapped[str] = mapped_column(String(50), default="0,3,7,15")
    
    # Feature Defaults
    default_plan_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_recording_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    default_storage_gb: Mapped[int] = mapped_column(Integer, default=50)
    
    # Email Template Subjects & Bodies
    invoice_reminder_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    renewal_reminder_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    trial_expiry_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    payment_success_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    payment_failed_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    welcome_template: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


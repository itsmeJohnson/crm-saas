from datetime import datetime
from sqlalchemy import String, Boolean, Integer
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
    extra_storage_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Profile Extensions
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    support_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata", nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="English", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    # Billing Extensions
    billing_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_pin_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Notification settings
    notification_invoice_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_renewal_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_support_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Extra Portal Fields
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    theme: Mapped[str] = mapped_column(String(50), default="dark", nullable=False)

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


import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Numeric, DateTime, JSON, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class Invoice(BaseModel):
    __tablename__ = "invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Pending")  # Paid, Pending, Overdue
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Billing extensions
    plan_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_inr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), default="unpaid", nullable=False)  # paid, unpaid, overdue

    # Detailed commercial invoicing
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    setup_charges: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    extra_users_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    gst_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    pdf_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    action_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


    # Multi-currency support (Phase 6)
    base_currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    invoice_currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(15, 6), default=1.0, nullable=False)
    base_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    converted_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    # Tax engine (Phase 7)
    tax_type: Mapped[str] = mapped_column(String(20), default="GST", nullable=False)
    tax_label: Mapped[str] = mapped_column(String(50), default="GST @18%", nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=18.0, nullable=False)
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Credit note
    is_credit_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    credit_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Billing detail
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    billing_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seats_billed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invoice_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coupon_discount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")


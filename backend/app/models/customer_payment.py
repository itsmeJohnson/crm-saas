import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class CustomerPayment(BaseModel):
    """A payment received from a customer against a tenant-issued invoice.

    Manual/recorded receipts (no live gateway collection yet).
    """
    __tablename__ = "customer_payments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    method: Mapped[str] = mapped_column(String(30), default="BankTransfer", nullable=False)  # Cash|BankTransfer|Card|UPI|Cheque|Other
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    invoice: Mapped["CustomerInvoice"] = relationship("CustomerInvoice", back_populates="payments")

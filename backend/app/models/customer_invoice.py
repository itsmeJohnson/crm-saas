import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class CustomerInvoice(BaseModel):
    """A tenant-issued invoice to one of ITS customers (accounts receivable).

    Separate from the platform `invoices` table (SaaS -> tenant billing).
    """
    __tablename__ = "customer_invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Draft", nullable=False, index=True)  # Draft|Sent|PartiallyPaid|Paid|Overdue|Void
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    payments: Mapped[list["CustomerPayment"]] = relationship(
        "CustomerPayment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def balance_due(self) -> float:
        return float(self.total_amount or 0) - float(self.amount_paid or 0)

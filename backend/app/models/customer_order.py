import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CustomerOrder(BaseModel):
    """A tenant's sales order to one of ITS customers (a Company/Contact).

    Distinct from platform billing (invoices/payments tables), which is the SaaS
    charging tenant organizations. Line items live in the JSON `items` column.
    """
    __tablename__ = "customer_orders"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Draft", nullable=False, index=True)  # Draft|Confirmed|Fulfilled|Cancelled
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{description, quantity, unit_price, amount}]
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

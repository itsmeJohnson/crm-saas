import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class Payment(BaseModel):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)  # "UPI", "Bank", "Manual", "Stripe", etc.
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False)  # "Paid", "Pending", "Failed"
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

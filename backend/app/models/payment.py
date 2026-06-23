import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime
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

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Numeric, DateTime
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

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")

import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Numeric, Date, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Expense(BaseModel):
    """A business expense — the one financial input not already in the CRM's
    order-to-cash data. Powers Financial Analytics' Expenses, Profitability and
    (via acquisition-category spend) CAC. Org-scoped."""
    __tablename__ = "expenses"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), default="General", nullable=False, index=True)  # e.g. Marketing|Sales|Payroll|Software|Office|General
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    incurred_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_expenses_org_incurred", "organization_id", "incurred_at"),
    )

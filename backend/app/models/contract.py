import uuid
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, Numeric, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Contract(BaseModel):
    """A contract/agreement between the tenant and one of its customers."""
    __tablename__ = "contracts"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    contract_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Draft", nullable=False, index=True)  # Draft|Active|Expired|Terminated|Renewed
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    renewal_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

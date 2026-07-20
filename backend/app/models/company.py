import uuid
from sqlalchemy import String, ForeignKey, Integer, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Company(BaseModel):
    __tablename__ = "companies"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_type: Mapped[str] = mapped_column(String(30), default="Prospect", nullable=False, index=True)  # Prospect|Customer|Partner
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of strings
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of {filename, url, size, uploaded_by, uploaded_at}

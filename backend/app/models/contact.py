import uuid
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Contact(BaseModel):
    __tablename__ = "contacts"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of strings
    custom_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {definition_key: value}
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of {filename, url, size, uploaded_by, uploaded_at}

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class Lead(BaseModel):
    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="New", nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Medium", nullable=False, index=True)  # "Low", "Medium", "High", "Urgent"
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    import_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead_imports.id"), nullable=True, index=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipeline_stages.id"), nullable=False, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    call_attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of {filename, url, size, uploaded_by, uploaded_at}
    converted_contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    # Branch & Territory (nullable — backward compatible; populated by PIN/city
    # resolution or explicit assignment. Existing leads stay NULL.)
    pin_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    territory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("territories.id"), nullable=True, index=True)

    # Relationships
    import_batch: Mapped["LeadImport | None"] = relationship("LeadImport", back_populates="leads")
    stage: Mapped["PipelineStage"] = relationship("PipelineStage", back_populates="leads")

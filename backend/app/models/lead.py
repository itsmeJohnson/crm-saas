import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Integer
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="New", nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    import_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead_imports.id"), nullable=True, index=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipeline_stages.id"), nullable=False, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    call_attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    import_batch: Mapped["LeadImport | None"] = relationship("LeadImport", back_populates="leads")
    stage: Mapped["PipelineStage"] = relationship("PipelineStage", back_populates="leads")

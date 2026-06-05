import uuid
import enum
from sqlalchemy import String, Integer, Float, ForeignKey, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class LeadImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    PREVIEW_READY = "PREVIEW_READY"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

class LeadImport(BaseModel):
    __tablename__ = "lead_imports"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LeadImportStatus] = mapped_column(Enum(LeadImportStatus, native_enum=False), default=LeadImportStatus.PENDING, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_summary: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failed_rows_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User"] = relationship("User")
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="import_batch")

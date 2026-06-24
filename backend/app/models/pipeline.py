import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class PipelineStage(BaseModel):
    __tablename__ = "pipeline_stages"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order_position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_system_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Unique constraints
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_pipeline_stages_organization_name"),
        UniqueConstraint("organization_id", "order_position", name="uq_pipeline_stages_organization_order"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="stage")

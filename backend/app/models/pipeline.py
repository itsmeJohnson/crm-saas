import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Pipeline(BaseModel):
    """Metadata-driven sales pipeline for a tenant organization."""
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_pipelines_organization_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    stages: Mapped[list["PipelineStage"]] = relationship(
        "PipelineStage",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStage.order_position.asc()",
        lazy="selectin"
    )
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="pipeline")


class PipelineStage(BaseModel):
    """Specific stage inside a sales pipeline."""
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "name", name="uq_pipeline_stages_pipeline_name"),
        UniqueConstraint("pipeline_id", "order_position", name="uq_pipeline_stages_pipeline_order"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order_position: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#4F46E5", nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="stages")
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="stage")



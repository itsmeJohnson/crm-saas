import uuid
from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Visualization(BaseModel):
    """A saved visualization: a viz type + dataset + config rendered on demand by
    VisualizationService over the Report Builder's safe query engine. Distinct
    from ReportDefinition (tabular reports) — this stores chart-first specs
    (heatmap axes, funnel stages, gauge targets, geo fields, ...)."""
    __tablename__ = "visualizations"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    viz_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # one of VIZ_TYPES
    dataset: Mapped[str] = mapped_column(String(30), nullable=False)  # report-builder dataset key
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # per-type settings (dimension/measure/…)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # rule-engine group format
    visibility: Mapped[str] = mapped_column(String(16), default="organization", nullable=False)  # private|organization
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)  # Home dashboard
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

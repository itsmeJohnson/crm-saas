import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Boolean, Integer, Numeric, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class MetricSnapshot(BaseModel):
    """One org-level metric value captured on one date — the historical
    time-series store behind Historical Analytics. Daily rows are captured by
    the cron from the KPI engine's cross-domain metric snapshot; rows older than
    the retention window are compacted into monthly (granularity='monthly')
    archive rows. Also exposed as the `metric_history` Report Builder dataset,
    so the whole export/BI stack can read it (data-warehouse ready)."""
    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("organization_id", "snapshot_date", "metric", "granularity",
                                       name="uq_metric_snapshot"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    granularity: Mapped[str] = mapped_column(String(8), default="daily", nullable=False, index=True)  # daily|monthly


class HistorySetting(BaseModel):
    """Org-singleton retention policy for the snapshot store: daily rows older
    than retention_days are archived to monthly averages (when enabled) and the
    daily rows deleted."""
    __tablename__ = "history_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_history_settings_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=730, nullable=False)
    archive_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

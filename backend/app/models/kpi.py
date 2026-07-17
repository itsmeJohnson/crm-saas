"""KPI Engine models.

A `KPIDefinition` is a user-configured key performance indicator: a metric drawn
from the catalog (or a manually-entered value), a target and warning/critical
thresholds, and a comparison direction. The engine evaluates each KPI against the
live metric snapshot, and records a `KPIAlert` (and notifies) when a threshold is
breached. Distinct from the per-user PerformanceKPI (which drives performance
goals) — this is the org-wide, cross-domain KPI/alerting layer.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Text, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class KPIDefinition(BaseModel):
    __tablename__ = "kpi_definitions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(24), default="custom", nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)          # catalog key or "manual"
    unit: Mapped[str] = mapped_column(String(12), default="count", nullable=False)  # count|percent|currency
    comparison: Mapped[str] = mapped_column(String(16), default="higher_better", nullable=False)  # higher_better|lower_better
    target_value: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    warning_value: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    critical_value: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    manual_value: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)  # for metric="manual"
    window_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notify: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)   # recipient roles (default OrgAdmin)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_kpi_definitions_org_active", "organization_id", "is_active"),
    )


class KPIAlert(BaseModel):
    """An open/resolved threshold breach for a KPI — powers Alerts + Reports and
    dedups repeat notifications (one open alert per KPI)."""
    __tablename__ = "kpi_alerts"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    kpi_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kpi_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="warning", nullable=False, index=True)  # warning|critical
    value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

"""Custom Report Builder models.

A `ReportDefinition` is a saved, metadata-driven query over an existing dataset
(leads/contacts/companies/tasks/activities/invoices). It is NOT raw SQL — the
engine reads only the whitelisted columns/relations in the dataset catalog,
always org-scoped. Definitions can be templated, shared, scheduled, versioned
and pinned to the dashboard. `ReportVersion` snapshots every change for rollback.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ReportDefinition(BaseModel):
    __tablename__ = "report_definitions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # catalog key
    columns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)      # [{field, label?, agg?}]
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)              # rule_evaluator tree
    group_by: Mapped[list | None] = mapped_column(JSON, nullable=True)            # [field, ...]
    sort: Mapped[list | None] = mapped_column(JSON, nullable=True)                # [{field, dir}]
    calculated_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{name, expression, type}]
    pivot: Mapped[dict | None] = mapped_column(JSON, nullable=True)               # {row, col, measure, agg}
    chart: Mapped[dict | None] = mapped_column(JSON, nullable=True)               # {type, x, y}
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private", nullable=False)  # private|organization
    pinned_to_dashboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # scheduling
    schedule_frequency: Mapped[str | None] = mapped_column(String(12), nullable=True)  # daily|weekly|monthly
    schedule_recipients: Mapped[list | None] = mapped_column(JSON, nullable=True)       # [user_id, ...]
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_report_definitions_org_dataset", "organization_id", "dataset"),
    )


class ReportVersion(BaseModel):
    __tablename__ = "report_versions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

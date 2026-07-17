import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, Integer, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class BIToken(BaseModel):
    """A per-org API key for BI tools (Power BI / Tableau / Looker / Metabase).
    Grants read-only access to the token-authenticated data feed endpoints —
    no JWT login flow, so external tools can pull directly. Follows the calendar
    feed_token precedent."""
    __tablename__ = "bi_tokens"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    datasets: Mapped[list | None] = mapped_column(JSON, nullable=True)  # allowed dataset keys; None = all
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class BISetting(BaseModel):
    """Org-singleton export settings: cloud-storage destination (local directory
    by default, S3-compatible when configured). Mirrors the sms/email/whatsapp
    per-org settings pattern."""
    __tablename__ = "bi_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_bi_settings_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    storage_provider: Mapped[str] = mapped_column(String(12), default="local", nullable=False)  # local|s3
    s3_bucket: Mapped[str | None] = mapped_column(String(200), nullable=True)
    s3_region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    s3_access_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    s3_secret_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    s3_prefix: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ExportJob(BaseModel):
    """Audit-grade history of every export: downloads, webhook pushes, cloud
    uploads and data-sync runs — with rows, size, target and outcome."""
    __tablename__ = "export_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, index=True)  # download|webhook|cloud|sync
    source_type: Mapped[str] = mapped_column(String(12), default="dataset", nullable=False)  # dataset|report
    source_key: Mapped[str] = mapped_column(String(64), nullable=False)  # dataset key or report id
    format: Mapped[str] = mapped_column(String(8), default="csv", nullable=False)  # csv|xlsx|pdf|json
    target: Mapped[str | None] = mapped_column(String(500), nullable=True)  # URL or storage path
    status: Mapped[str] = mapped_column(String(12), default="success", nullable=False, index=True)  # success|failed
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None for cron syncs


class BISyncConfig(BaseModel):
    """Data Sync: a recurring push of a dataset/report export to a webhook URL
    or cloud storage — full snapshots or incremental (created_at cursor)."""
    __tablename__ = "bi_sync_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_type: Mapped[str] = mapped_column(String(12), default="dataset", nullable=False)  # dataset|report
    source_key: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(8), default="json", nullable=False)  # json|csv|xlsx
    destination: Mapped[str] = mapped_column(String(12), default="webhook", nullable=False)  # webhook|cloud
    target_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # webhook destination
    path_prefix: Mapped[str | None] = mapped_column(String(200), nullable=True)  # cloud destination folder
    mode: Mapped[str] = mapped_column(String(12), default="full", nullable=False)  # full|incremental
    last_cursor: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ISO created_at watermark
    frequency: Mapped[str] = mapped_column(String(12), default="daily", nullable=False)  # daily|weekly|monthly
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

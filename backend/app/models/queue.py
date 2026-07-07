import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, JSON, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class QueueJob(BaseModel):
    """A durable background job on a named queue.

    Persisted (Postgres-backed, poll-based worker) — no external broker, matching
    the app's single-scheduler + redis-lock architecture. Supports priority
    ordering, retry with a dead-letter terminus, scheduled `run_at`, cancellation
    and full history.

    queue   ∈ email | sms | whatsapp | report | export | ai | default
    job_type: handler key (send_email, generate_report, ai_task, …)
    status  ∈ queued | running | succeeded | failed | dead_letter | cancelled
    """
    __tablename__ = "queue_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    queue: Mapped[str] = mapped_column(String(20), default="default", nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False, index=True)  # higher = sooner
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        # the claim query filters on (status, run_at) and orders by priority
        Index("ix_queue_jobs_claim", "status", "run_at", "priority"),
    )


class QueueWorker(BaseModel):
    """A registered queue worker (the async loop that claims + runs jobs).
    Heartbeats let the dashboard show liveness and flag stale/offline workers."""
    __tablename__ = "queue_workers"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="idle", nullable=False)  # idle | busy | offline
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    queues: Mapped[str | None] = mapped_column(String(200), nullable=True)  # csv of queues this worker serves

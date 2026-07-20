import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class EnqueueRequest(BaseModel):
    job_type: str
    payload: dict | None = None
    queue: str | None = None
    priority: int = 5
    max_attempts: int = 3
    run_at: datetime | None = None


class JobResponse(BaseModel):
    id: str
    queue: str
    job_type: str
    priority: int
    status: str
    attempts: int
    max_attempts: int
    payload: dict | None = None
    result: dict | None = None
    error: str | None = None
    run_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    created_at: str | None = None


class WorkerResponse(BaseModel):
    id: str
    name: str
    status: str
    last_heartbeat: str | None = None
    jobs_processed: int
    current_job_id: str | None = None
    queues: str | None = None


class QueueDashboard(BaseModel):
    pending: int
    running: int
    succeeded: int
    failed: int
    dead_letter: int
    workers: int
    recent: list[dict]


class QueueReport(BaseModel):
    total: int
    by_queue: dict
    success_rate: float
    avg_duration_ms: float


class PurgeRequest(BaseModel):
    status: str


class SimpleResult(BaseModel):
    purged: int = 0

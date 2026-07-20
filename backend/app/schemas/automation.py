import uuid
from pydantic import BaseModel, Field


# ---------- jobs ----------
class JobResponse(BaseModel):
    id: str | None = None
    job_key: str
    name: str
    category: str
    description: str | None = None
    is_enabled: bool
    schedule: str
    max_retries: int
    last_run_at: str | None = None
    last_status: str | None = None
    next_run_at: str | None = None
    run_count: int
    fail_count: int


class EnableRequest(BaseModel):
    enabled: bool


class JobConfigRequest(BaseModel):
    max_retries: int | None = None
    schedule: str | None = None


class RunResponse(BaseModel):
    id: str
    job_key: str
    status: str
    triggered_by: str
    items_processed: int
    retry_count: int
    error: str | None = None
    duration_ms: int | None = None
    started_at: str | None = None
    finished_at: str | None = None


# ---------- SLA ----------
class SLACreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    entity_type: str = "lead"
    metric: str = "first_response"
    threshold_hours: float = 24.0
    conditions: dict | None = None
    on_breach: str = "notify_manager"
    is_active: bool = True


class SLAUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    entity_type: str | None = None
    metric: str | None = None
    threshold_hours: float | None = None
    conditions: dict | None = None
    on_breach: str | None = None
    is_active: bool | None = None


class SLAResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    entity_type: str
    metric: str
    threshold_hours: float
    conditions: dict | None = None
    on_breach: str
    is_active: bool
    breach_count: int
    created_at: str | None = None


class BreachResponse(BaseModel):
    id: str
    policy_id: str
    entity_type: str
    entity_id: str
    metric: str
    hours_elapsed: float
    resolved: bool
    notified: bool
    breached_at: str | None = None


# ---------- scheduled reports ----------
class ReportCreate(BaseModel):
    name: str = Field(..., max_length=150)
    report_type: str = "lead_summary"
    frequency: str = "weekly"
    channel: str = "in_app"
    recipients: list[str] = []
    is_active: bool = True


class ReportUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    report_type: str | None = None
    frequency: str | None = None
    channel: str | None = None
    recipients: list[str] | None = None
    is_active: bool | None = None


class ScheduledReportResponse(BaseModel):
    id: str
    name: str
    report_type: str
    frequency: str
    channel: str
    recipients: list[str]
    is_active: bool
    last_sent_at: str | None = None
    next_run_at: str | None = None
    send_count: int


# ---------- dashboard / report ----------
class AutomationReport(BaseModel):
    total_runs: int
    failed: int
    succeeded: int
    success_rate: float
    runs_by_job: dict
    open_breaches: int
    active_reports: int


class AutomationDashboard(BaseModel):
    jobs: int
    enabled: int
    success_rate: float
    open_breaches: int
    active_reports: int
    recent: list[dict]


class SimpleResult(BaseModel):
    delivered: int = 0

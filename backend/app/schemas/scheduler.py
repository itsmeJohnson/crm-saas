from datetime import datetime
from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    task_type: str
    task_config: dict | None = None
    schedule_kind: str = "daily"
    cron_expr: str | None = None
    time_of_day: str | None = None          # "HH:MM"
    day_of_week: int | None = None          # 0=Mon..6=Sun
    day_of_month: int | None = None         # 1..31
    interval_minutes: int | None = None
    timezone: str = "UTC"
    business_hours_only: bool = False
    skip_holidays: bool = False
    is_active: bool = True
    max_retries: int = 1


class ScheduleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    task_type: str | None = None
    task_config: dict | None = None
    schedule_kind: str | None = None
    cron_expr: str | None = None
    time_of_day: str | None = None
    day_of_week: int | None = None
    day_of_month: int | None = None
    interval_minutes: int | None = None
    timezone: str | None = None
    business_hours_only: bool | None = None
    skip_holidays: bool | None = None
    is_active: bool | None = None
    max_retries: int | None = None


class ScheduleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    task_type: str
    task_config: dict | None = None
    schedule_kind: str
    cron_expr: str | None = None
    time_of_day: str | None = None
    day_of_week: int | None = None
    day_of_month: int | None = None
    interval_minutes: int | None = None
    timezone: str
    business_hours_only: bool
    skip_holidays: bool
    is_active: bool
    max_retries: int
    last_run_at: str | None = None
    last_status: str | None = None
    next_run_at: str | None = None
    run_count: int
    fail_count: int
    skip_count: int


class RunResponse(BaseModel):
    id: str
    schedule_id: str
    status: str
    reason: str | None = None
    triggered_by: str
    attempts: int
    error: str | None = None
    result: dict | None = None
    scheduled_for: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


class EnableRequest(BaseModel):
    enabled: bool


class SchedulerReport(BaseModel):
    total: int
    active: int
    inactive: int
    runs: int
    failed: int
    skipped: int
    success_rate: float


class SchedulerDashboard(BaseModel):
    total: int
    active: int
    success_rate: float
    failed: int
    skipped: int
    upcoming: list[dict]
    recent: list[dict]

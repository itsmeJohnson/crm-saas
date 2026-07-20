import uuid
from typing import Any
from pydantic import BaseModel, Field


class ReportColumn(BaseModel):
    field: str
    label: str | None = None
    agg: str | None = None


class ReportCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    dataset: str
    columns: list[dict] = []
    filters: dict | None = None
    group_by: list[str] | None = None
    sort: list[dict] | None = None
    calculated_fields: list[dict] | None = None
    pivot: dict | None = None
    chart: dict | None = None
    is_template: bool = False
    visibility: str = "private"
    pinned_to_dashboard: bool = False


class ReportUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    dataset: str | None = None
    columns: list[dict] | None = None
    filters: dict | None = None
    group_by: list[str] | None = None
    sort: list[dict] | None = None
    calculated_fields: list[dict] | None = None
    pivot: dict | None = None
    chart: dict | None = None
    visibility: str | None = None
    pinned_to_dashboard: bool | None = None


class ReportResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    dataset: str
    columns: list[dict]
    filters: dict | None = None
    group_by: list[str] | None = None
    sort: list[dict] | None = None
    calculated_fields: list[dict] | None = None
    pivot: dict | None = None
    chart: dict | None = None
    is_template: bool
    visibility: str
    pinned_to_dashboard: bool
    schedule_frequency: str | None = None
    schedule_recipients: list[str] = []
    next_run: str | None = None
    last_run: str | None = None
    run_count: int
    version: int
    created_by: str
    created_at: str | None = None


class RunResult(BaseModel):
    columns: list[dict]
    rows: list[dict]
    total: int
    scanned: int | None = None
    pivot: dict | None = None
    chart: dict | None = None


class PreviewRequest(ReportCreate):
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class ScheduleRequest(BaseModel):
    schedule_frequency: str | None = None
    schedule_recipients: list[uuid.UUID] | None = None


class RestoreRequest(BaseModel):
    version_no: int


class VersionRow(BaseModel):
    id: str
    version_no: int
    note: str | None = None
    snapshot: dict
    created_at: str | None = None


class SimpleCreated(BaseModel):
    created: int = 0

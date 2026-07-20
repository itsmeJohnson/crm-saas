import uuid
from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    report_id: uuid.UUID
    name: str = Field(..., max_length=150)
    frequency: str = "weekly"
    formats: list[str] = ["csv"]
    channels: list[str] = ["notification"]
    recipients: list[str] = []
    extra_emails: list[str] | None = None
    is_active: bool = True
    max_retries: int = Field(2, ge=0, le=5)


class ScheduleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    frequency: str | None = None
    formats: list[str] | None = None
    channels: list[str] | None = None
    recipients: list[str] | None = None
    extra_emails: list[str] | None = None
    is_active: bool | None = None
    max_retries: int | None = Field(None, ge=0, le=5)

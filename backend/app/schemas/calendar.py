import uuid
from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    event_type: str = Field("Meeting", max_length=30)
    location: str | None = Field(None, max_length=255)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    assigned_user_id: uuid.UUID | None = None
    attendees: list[dict[str, Any]] | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str = Field("none", max_length=20)
    recurrence_until: date | None = None
    remind_at: datetime | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    event_type: str | None = Field(None, max_length=30)
    location: str | None = Field(None, max_length=255)
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    status: str | None = Field(None, max_length=20)
    assigned_user_id: uuid.UUID | None = None
    attendees: list[dict[str, Any]] | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str | None = Field(None, max_length=20)
    recurrence_until: date | None = None
    remind_at: datetime | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: str | None = None
    event_type: str
    location: str | None = None
    start_at: datetime
    end_at: datetime
    all_day: bool
    status: str
    assigned_user_id: uuid.UUID | None = None
    created_by: uuid.UUID
    attendees: list | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str
    recurrence_until: date | None = None
    remind_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CalendarItem(BaseModel):
    """A normalized item on the unified calendar (from any source)."""
    source: str          # event|task|activity|followup|holiday
    type: str
    id: str
    title: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    status: str | None = None
    link: str | None = None
    metadata: dict | None = None


# --- Holidays ---
class HolidayCreate(BaseModel):
    name: str = Field(..., max_length=150)
    holiday_date: date
    recurring_annual: bool = False


class HolidayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    holiday_date: date
    recurring_annual: bool


# --- Working hours ---
class WorkingHoursUpdate(BaseModel):
    timezone: str | None = Field(None, max_length=64)
    days: dict[str, Any] | None = None


class WorkingHoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    timezone: str
    days: dict


# --- Feed / reports ---
class FeedUrlResponse(BaseModel):
    url: str
    token: str


class CalendarReportResponse(BaseModel):
    total_events: int
    upcoming_7d: int
    by_type: list[dict]
    by_user: list[dict]
    tasks_due_7d: int

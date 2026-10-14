import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class BookingLinkCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    location: str | None = Field(None, max_length=255)
    host_user_id: uuid.UUID | None = None
    slot_minutes: int = Field(30, ge=5, le=480)
    buffer_minutes: int = Field(0, ge=0, le=240)
    advance_days: int = Field(14, ge=1, le=120)
    is_active: bool = True


class BookingLinkUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    location: str | None = Field(None, max_length=255)
    slot_minutes: int | None = Field(None, ge=5, le=480)
    buffer_minutes: int | None = Field(None, ge=0, le=240)
    advance_days: int | None = Field(None, ge=1, le=120)
    is_active: bool | None = None


class BookingLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    host_user_id: uuid.UUID
    slug: str
    title: str
    description: str | None = None
    location: str | None = None
    slot_minutes: int
    buffer_minutes: int
    advance_days: int
    is_active: bool
    bookings_count: int
    created_at: datetime


class PublicBookRequest(BaseModel):
    slot_start: str = Field(..., description="ISO 8601 start instant of the chosen slot")
    name: str = Field(..., min_length=1, max_length=150)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200)
    body: str
    audience: str = Field("all", pattern="^(all|OrgAdmin|Manager|Employee)$")
    is_pinned: bool = False
    is_active: bool = True
    published_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    body: str | None = None
    audience: str | None = Field(None, pattern="^(all|OrgAdmin|Manager|Employee)$")
    is_pinned: bool | None = None
    is_active: bool | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    body: str
    audience: str
    is_pinned: bool
    is_active: bool
    published_at: str | None = None
    expires_at: str | None = None
    author_name: str | None = None
    created_at: datetime

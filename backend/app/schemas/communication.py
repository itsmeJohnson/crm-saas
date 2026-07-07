import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

CHANNELS = ("Call", "SMS", "WhatsApp", "Email", "Note")


class CommunicationLog(BaseModel):
    channel: str = Field(..., max_length=20)          # Call|SMS|WhatsApp|Email|Note
    direction: str = Field("OUTBOUND", max_length=20)  # INBOUND|OUTBOUND
    subject: str = Field(..., max_length=255)
    body: str | None = None
    occurred_at: datetime | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    attachments: list | None = None
    send_email: bool = False  # if channel=Email, also send via the email service (optional)
    to_email: str | None = None


class CommunicationItem(BaseModel):
    id: str
    channel: str
    direction: str | None = None
    subject: str
    body: str | None = None
    status: str
    timestamp: datetime
    actor_user_id: str | None = None
    actor_name: str | None = None
    lead_id: str | None = None
    contact_id: str | None = None
    company_id: str | None = None
    recording_url: str | None = None
    attachments: list | None = None
    is_read: bool = True
    is_pinned: bool = False
    internal: bool = False


class ConversationSummary(BaseModel):
    entity_type: str            # contact|company|lead
    entity_id: str
    name: str
    last_channel: str
    last_subject: str
    last_at: datetime
    unread_count: int
    total: int
    pinned: bool = False


class CommunicationStats(BaseModel):
    total: int
    unread: int
    this_week: int
    by_channel: list[dict]
    by_direction: list[dict]


class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=150)
    channel: str = Field("Email", max_length=20)
    subject: str | None = Field(None, max_length=255)
    body: str = Field(..., min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    channel: str | None = Field(None, max_length=20)
    subject: str | None = Field(None, max_length=255)
    body: str | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    channel: str
    subject: str | None = None
    body: str
    created_at: datetime


class TemplateRenderRequest(BaseModel):
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None


class TemplateRenderResponse(BaseModel):
    subject: str | None = None
    body: str


class CommAttachmentResponse(BaseModel):
    filename: str
    url: str
    size: int | None = None
    uploaded_by: str | None = None
    uploaded_at: str | None = None

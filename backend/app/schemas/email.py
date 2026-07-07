import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EmailSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    auth_method: str
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_use_tls: bool
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_use_ssl: bool
    oauth_email: Optional[str] = None
    tracking_enabled: bool
    tracking_base_url: Optional[str] = None
    provider: str
    is_active: bool
    last_synced_at: Optional[datetime] = None
    # smtp_password / imap_password / oauth tokens are write-only secrets, never returned


class EmailSettingsUpdate(BaseModel):
    auth_method: Optional[str] = Field(None, max_length=30)
    from_email: Optional[str] = Field(None, max_length=320)
    from_name: Optional[str] = Field(None, max_length=150)
    smtp_host: Optional[str] = Field(None, max_length=255)
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_username: Optional[str] = Field(None, max_length=255)
    smtp_password: Optional[str] = Field(None, max_length=512)
    smtp_use_tls: Optional[bool] = None
    imap_host: Optional[str] = Field(None, max_length=255)
    imap_port: Optional[int] = Field(None, ge=1, le=65535)
    imap_username: Optional[str] = Field(None, max_length=255)
    imap_password: Optional[str] = Field(None, max_length=512)
    imap_use_ssl: Optional[bool] = None
    tracking_enabled: Optional[bool] = None
    tracking_base_url: Optional[str] = Field(None, max_length=255)
    provider: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class OAuthConnectRequest(BaseModel):
    provider: str = Field("google", max_length=20)  # google|microsoft
    email: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None


class EmailSendRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = ""
    to: Optional[str] = Field(None, max_length=1024)
    cc: Optional[str] = Field(None, max_length=1024)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None
    attachments: Optional[list] = None


class EmailReplyRequest(BaseModel):
    body: str = ""
    to: Optional[str] = None
    cc: Optional[str] = None
    attachments: Optional[list] = None


class EmailForwardRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=1024)
    cc: Optional[str] = None
    body: str = ""


class DraftCreate(BaseModel):
    subject: Optional[str] = Field(None, max_length=255)
    body: str = ""
    to: Optional[str] = None
    cc: Optional[str] = None
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None
    attachments: Optional[list] = None


class DraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    to: Optional[str] = None
    cc: Optional[str] = None
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None


class EmailItem(BaseModel):
    id: str
    direction: Optional[str] = None
    subject: str
    body: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None
    email_cc: Optional[str] = None
    status: Optional[str] = None
    is_draft: bool = False
    open_count: int = 0
    click_count: int = 0
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    thread_id: Optional[str] = None
    attachments: Optional[list] = None
    timestamp: datetime
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None


class EmailListResponse(BaseModel):
    items: List[EmailItem]
    total: int


class ThreadSummary(BaseModel):
    thread_id: str
    subject: str
    last_at: datetime
    count: int
    last_direction: Optional[str] = None
    opened: bool = False
    clicked: bool = False
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None


class ThreadDetail(BaseModel):
    thread_id: str
    subject: str
    messages: List[EmailItem]


class ReportBucket(BaseModel):
    label: str
    count: int


class EmailReportResponse(BaseModel):
    total: int
    sent: int
    inbound: int
    drafts: int
    failed: int
    opened: int
    clicked: int
    open_rate: float
    click_rate: float
    by_status: List[ReportBucket]
    by_direction: List[ReportBucket]
    by_day: List[ReportBucket]


class SyncResponse(BaseModel):
    ingested: int

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SmsSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    account_sid: Optional[str] = None
    sender_id: Optional[str] = None
    sms_priority: str = "ndnd"
    webhook_token: Optional[str] = None
    daily_limit: int
    is_active: bool
    # auth_token is intentionally omitted from responses (write-only secret)


class SmsSettingsUpdate(BaseModel):
    provider: Optional[str] = Field(None, max_length=30)
    account_sid: Optional[str] = Field(None, max_length=255)
    auth_token: Optional[str] = Field(None, max_length=255)
    sender_id: Optional[str] = Field(None, max_length=32)
    sms_priority: Optional[str] = Field(None, pattern="^(ndnd|dnd)$")
    daily_limit: Optional[int] = Field(None, ge=0, le=100000)
    is_active: Optional[bool] = None
    regenerate_webhook_token: bool = False


class SmsSendRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=1600)
    subject: Optional[str] = Field(None, max_length=255)
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None


class BulkRecipient(BaseModel):
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None


class SmsBulkRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=1600)
    subject: Optional[str] = Field(None, max_length=255)
    recipients: List[BulkRecipient] = Field(..., min_length=1, max_length=500)


class SmsBulkResult(BaseModel):
    total: int
    queued: int
    failed: int
    activity_ids: List[str]


class SmsItem(BaseModel):
    id: str
    direction: Optional[str] = None
    body: Optional[str] = None
    sms_status: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    segments: Optional[int] = None
    to_number: Optional[str] = None
    from_number: Optional[str] = None
    timestamp: datetime
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None


class SmsHistoryResponse(BaseModel):
    items: List[SmsItem]
    total: int


class ReportBucket(BaseModel):
    label: str
    count: int


class SmsReportResponse(BaseModel):
    total: int
    outbound: int
    inbound: int
    delivered: int
    failed: int
    segments: int
    delivery_rate: float
    by_status: List[ReportBucket]
    by_direction: List[ReportBucket]
    by_day: List[ReportBucket]


# ---- Webhook payloads (token-secured; no auth) ----
class SmsStatusWebhook(BaseModel):
    token: str
    provider_message_id: str
    status: str  # sent|delivered|failed|undelivered
    error: Optional[str] = None


class SmsInboundWebhook(BaseModel):
    token: str
    from_number: str
    to_number: Optional[str] = None
    body: str = ""
    provider_message_id: Optional[str] = None

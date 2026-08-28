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
    sms_type: str = "Transactional"
    default_template_id: Optional[str] = None
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
    sms_type: Optional[str] = Field(None, pattern="^(Transactional|Promotional|OTP)$")
    default_template_id: Optional[str] = Field(None, max_length=64)
    daily_limit: Optional[int] = Field(None, ge=0, le=100000)
    is_active: Optional[bool] = None
    regenerate_webhook_token: bool = False


# ---- Provider account info (BulkSMSPlans etc.) ----
class SmsBalanceResponse(BaseModel):
    success: bool
    amount: Optional[float] = None
    currency: Optional[str] = None
    message: Optional[str] = None


class SenderIdItem(BaseModel):
    sender_id: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None


class SenderIdListResponse(BaseModel):
    success: bool
    items: List[SenderIdItem] = []
    message: Optional[str] = None


class SenderIdRequest(BaseModel):
    sender: str = Field(..., min_length=1, max_length=32)
    country: str = Field("India", max_length=64)
    remarks: Optional[str] = Field(None, max_length=255)


class SenderIdRequestResult(BaseModel):
    success: bool
    message: Optional[str] = None


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


# ---- OTP verification ----
class OtpSendRequest(BaseModel):
    number: Optional[str] = Field(None, max_length=32)
    purpose: Optional[str] = Field(None, max_length=50)
    message: Optional[str] = Field(None, max_length=500)  # must contain {{otp}}
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    ttl_minutes: Optional[int] = Field(None, ge=1, le=60)
    max_attempts: Optional[int] = Field(None, ge=1, le=10)


class OtpVerifyRequest(BaseModel):
    verification_id: uuid.UUID
    otp: str = Field(..., min_length=1, max_length=12)


class OtpResponse(BaseModel):
    id: str
    number_masked: str
    purpose: Optional[str] = None
    status: str
    attempts: int
    max_attempts: int
    expires_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


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

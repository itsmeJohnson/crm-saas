import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WaSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    phone_number_id: Optional[str] = None
    business_account_id: Optional[str] = None
    sender_number: Optional[str] = None
    webhook_token: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    daily_limit: int
    auto_reply_enabled: bool
    auto_reply_message: Optional[str] = None
    is_active: bool
    # access_token intentionally omitted (write-only secret)


class WaSettingsUpdate(BaseModel):
    provider: Optional[str] = Field(None, max_length=30)
    phone_number_id: Optional[str] = Field(None, max_length=64)
    business_account_id: Optional[str] = Field(None, max_length=64)
    access_token: Optional[str] = None
    sender_number: Optional[str] = Field(None, max_length=32)
    daily_limit: Optional[int] = Field(None, ge=0, le=100000)
    auto_reply_enabled: Optional[bool] = None
    auto_reply_message: Optional[str] = None
    is_active: Optional[bool] = None
    regenerate_webhook_token: bool = False
    regenerate_verify_token: bool = False


class WaSendTextRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4096)
    conversation_id: Optional[uuid.UUID] = None
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None


class WaSendTemplateRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None
    template_name: Optional[str] = Field(None, max_length=128)
    body: Optional[str] = None
    conversation_id: Optional[uuid.UUID] = None
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None


class WaMessageItem(BaseModel):
    id: str
    direction: Optional[str] = None
    body: Optional[str] = None
    wa_status: Optional[str] = None
    media_type: Optional[str] = None
    template_name: Optional[str] = None
    error: Optional[str] = None
    attachments: Optional[list] = None
    timestamp: datetime
    from_number: Optional[str] = None
    to_number: Optional[str] = None


class WaConversationItem(BaseModel):
    id: str
    phone: str
    display_name: Optional[str] = None
    status: str
    unread_count: int
    assigned_user_id: Optional[str] = None
    assigned_user_name: Optional[str] = None
    window_open: bool
    window_expires_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None


class WaThreadResponse(BaseModel):
    conversation: WaConversationItem
    messages: List[WaMessageItem]


class WaAssignRequest(BaseModel):
    user_id: Optional[uuid.UUID] = None  # null unassigns


class QuickReplyCreate(BaseModel):
    shortcut: str = Field(..., min_length=1, max_length=50)
    text: str = Field(..., min_length=1)


class QuickReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    shortcut: str
    text: str


class ReportBucket(BaseModel):
    label: str
    count: int


class WaReportResponse(BaseModel):
    total: int
    outbound: int
    inbound: int
    delivered: int
    read: int
    failed: int
    delivery_rate: float
    read_rate: float
    by_status: List[ReportBucket]
    by_direction: List[ReportBucket]
    by_media_type: List[ReportBucket]
    by_day: List[ReportBucket]


# ---- Webhook payloads (token-secured; no auth) ----
class WaStatusWebhook(BaseModel):
    token: str
    message_id: str
    status: str  # sent|delivered|read|failed


class WaInboundWebhook(BaseModel):
    token: str
    from_number: str
    body: str = ""
    message_id: Optional[str] = None
    media_type: Optional[str] = None  # image|video|document|audio
    media_url: Optional[str] = None

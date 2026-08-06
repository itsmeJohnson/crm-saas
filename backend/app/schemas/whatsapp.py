import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class WaSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    friendly_name: Optional[str] = None
    phone_number_id: Optional[str] = None
    business_account_id: Optional[str] = None
    sender_number: Optional[str] = None
    meta_app_id: Optional[str] = None
    webhook_token: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    webhook_url: Optional[str] = None
    api_version: str
    default_country_code: str
    daily_limit: int
    auto_reply_enabled: bool
    auto_reply_message: Optional[str] = None
    is_active: bool
    health_status: str
    is_default: bool
    quality_rating: Optional[str] = None
    messaging_limit: Optional[str] = None
    display_name_status: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    # access_token and webhook_secret_enc intentionally omitted (write-only secrets)


class WaSettingsUpdate(BaseModel):
    provider: Optional[str] = Field(None, max_length=30)
    friendly_name: Optional[str] = Field(None, max_length=100)
    phone_number_id: Optional[str] = Field(None, max_length=64)
    business_account_id: Optional[str] = Field(None, max_length=64)
    access_token: Optional[str] = None
    sender_number: Optional[str] = Field(None, max_length=32)
    meta_app_id: Optional[str] = Field(None, max_length=64)
    webhook_verify_token: Optional[str] = Field(None, max_length=64)
    webhook_secret: Optional[str] = None
    webhook_url: Optional[str] = Field(None, max_length=255)
    api_version: Optional[str] = Field(None, max_length=20)
    default_country_code: Optional[str] = Field(None, max_length=10)
    daily_limit: Optional[int] = Field(None, ge=0, le=100000)
    auto_reply_enabled: Optional[bool] = None
    auto_reply_message: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    quality_rating: Optional[str] = None
    messaging_limit: Optional[str] = None
    display_name_status: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    regenerate_webhook_token: bool = False
    regenerate_verify_token: bool = False


class WaContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    phone: str
    display_name: Optional[str] = None


class WaLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    color: str


class WaLabelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field("#10B981", max_length=20)


class WaAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    media_id: Optional[str] = None
    media_url: str
    media_type: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    local_path: Optional[str] = None


class WhatsAppMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    body: Optional[str] = None
    wa_message_id: Optional[str] = None
    wa_status: str
    media_type: str
    template_name: Optional[str] = None
    error: Optional[str] = None
    is_internal: bool
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    retry_count: int
    attachments: List[WaAttachmentResponse] = []
    created_at: datetime
    
    # AI readiness fields
    ai_summary: Optional[str] = None
    ai_sentiment: Optional[str] = None
    ai_intent: Optional[str] = None
    suggested_reply: Optional[str] = None
    language: Optional[str] = None
    translation: Optional[str] = None


class WaSendTextRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4096)
    conversation_id: Optional[uuid.UUID] = None
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    settings_id: Optional[uuid.UUID] = None  # Specific phone number configuration
    is_internal: bool = False


class WaSendTemplateRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None
    template_name: Optional[str] = Field(None, max_length=128)
    body: Optional[str] = None
    conversation_id: Optional[uuid.UUID] = None
    to_number: Optional[str] = Field(None, max_length=32)
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    settings_id: Optional[uuid.UUID] = None
    language: str = "en_US"
    variables: Optional[List[str]] = None  # Dynamic body parameter values


class WaConversationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    whatsapp_settings_id: uuid.UUID
    phone: str
    display_name: Optional[str] = None
    status: str
    is_pinned: bool
    unread_count: int
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    window_open: bool
    window_expires_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    lead_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    whatsapp_contact_id: Optional[uuid.UUID] = None
    
    # SLA metrics
    sla_status: str
    sla_due_at: Optional[datetime] = None
    
    # Lock Lease
    locked_by_user_id: Optional[uuid.UUID] = None
    locked_by_user_name: Optional[str] = None
    lock_expires_at: Optional[datetime] = None
    is_locked: bool = False
    
    labels: List[WaLabelResponse] = []


class WaThreadResponse(BaseModel):
    conversation: WaConversationItem
    messages: List[WhatsAppMessageResponse]


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
    response_time_avg_sec: float
    by_status: List[ReportBucket]
    by_direction: List[ReportBucket]
    by_media_type: List[ReportBucket]
    by_day: List[ReportBucket]


class WhatsAppTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    meta_template_id: Optional[str] = None
    name: str
    category: str
    language: str
    status: str
    header_format: Optional[str] = None
    header_text: Optional[str] = None
    body_text: str
    footer_text: Optional[str] = None
    buttons: Optional[Dict[str, Any]] = None


# ---- Webhook payloads (token-secured; no auth) ----
class WaStatusWebhook(BaseModel):
    token: str
    message_id: str
    status: str  # sent|delivered|read|failed
    timestamp: Optional[datetime] = None
    error: Optional[str] = None


class WaInboundWebhook(BaseModel):
    token: str
    from_number: str
    body: str = ""
    message_id: Optional[str] = None
    media_type: Optional[str] = None  # image|video|document|audio|location|contacts
    media_url: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None  # dynamic variables (coordinates, contacts)


class WhatsAppSignupExchange(BaseModel):
    code: str
    redirect_uri: str


class WaDashboardMetrics(BaseModel):
    connected_accounts: int
    disconnected_accounts: int
    expired_tokens: int
    rate_limited_accounts: int
    maintenance_accounts: int
    quality_ratings: List[Dict[str, Any]]
    messaging_limits: List[Dict[str, Any]]
    webhook_status: str
    template_sync_status: str
    last_sync_time: str
    graph_api_latency_ms: int
    queue_size: int
    queue_health: str
    failed_messages: int
    success_rate: float
    daily_volume: int

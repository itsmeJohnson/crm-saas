import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    channel: str
    template_id: Optional[uuid.UUID] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: str
    audience_type: str
    audience_definition: Optional[dict] = None
    segment_id: Optional[uuid.UUID] = None
    entity_type: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    opened_count: int
    clicked_count: int
    converted_count: int
    cost_per_message: float
    revenue: float
    max_retries: int
    created_by: uuid.UUID
    created_at: datetime


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    channel: str = Field(..., max_length=20)  # SMS|Email|WhatsApp|Call
    template_id: Optional[uuid.UUID] = None
    subject: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    audience_type: str = Field("filter", max_length=20)  # filter|list|segment
    audience_definition: Optional[dict] = None
    segment_id: Optional[uuid.UUID] = None
    entity_type: str = Field("lead", max_length=20)  # lead|contact
    cost_per_message: float = 0
    max_retries: int = Field(2, ge=0, le=10)


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    subject: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    template_id: Optional[uuid.UUID] = None
    audience_type: Optional[str] = None
    audience_definition: Optional[dict] = None
    segment_id: Optional[uuid.UUID] = None
    entity_type: Optional[str] = None
    cost_per_message: Optional[float] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class AudiencePreviewReq(BaseModel):
    channel: str = "SMS"
    entity_type: str = "lead"
    audience_type: str = "filter"
    audience_definition: Optional[dict] = None
    segment_id: Optional[uuid.UUID] = None
    ids: Optional[List[uuid.UUID]] = None


class AudiencePreviewResp(BaseModel):
    count: int
    sample_ids: List[str]
    channel: str
    entity_type: str


class BuildReq(BaseModel):
    ids: Optional[List[uuid.UUID]] = None


class ScheduleReq(BaseModel):
    scheduled_at: datetime


class CampaignReport(BaseModel):
    campaign_id: str
    name: str
    channel: str
    status: str
    total_recipients: int
    sent: int
    delivered: int
    failed: int
    opened: int
    clicked: int
    converted: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    conversion_rate: float
    cost: float
    revenue: float
    roi: float
    roi_pct: float


class RecipientItem(BaseModel):
    id: str
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    to_address: Optional[str] = None
    status: str
    error: Optional[str] = None
    retry_count: int
    activity_id: Optional[str] = None
    sent_at: Optional[datetime] = None


class RecipientList(BaseModel):
    items: List[RecipientItem]
    total: int


class ReportBucket(BaseModel):
    label: str
    count: int


class CampaignDashboard(BaseModel):
    total: int
    running: int
    scheduled: int
    completed: int
    total_sent: int
    total_converted: int
    total_revenue: float
    total_roi: float
    by_status: List[ReportBucket]


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    entity_type: str
    definition: dict
    cached_count: Optional[int] = None
    created_at: datetime


class SegmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    entity_type: str = Field("lead", max_length=20)
    definition: dict = {}


class SegmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entity_type: Optional[str] = None
    definition: Optional[dict] = None

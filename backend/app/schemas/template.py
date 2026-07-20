import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    channel: str
    subject: Optional[str] = None
    body: str
    category: Optional[str] = None
    description: Optional[str] = None
    status: str
    version: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime


class TemplateCreateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    channel: str = Field("Email", max_length=20)  # Email|SMS|WhatsApp|Call
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1)
    category: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class TemplateUpdateReq(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    channel: Optional[str] = Field(None, max_length=20)
    subject: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    category: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    change_note: Optional[str] = Field(None, max_length=255)


class RejectReq(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class PreviewReq(BaseModel):
    contact_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None


class PreviewResp(BaseModel):
    channel: str
    subject: Optional[str] = None
    body: str


class TestSendReq(BaseModel):
    to: Optional[str] = None
    contact_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None


class TestSendResp(BaseModel):
    sent: bool
    channel: str
    activity_id: Optional[str] = None
    preview: Optional[str] = None


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    name: str
    channel: str
    subject: Optional[str] = None
    body: str
    category: Optional[str] = None
    change_note: Optional[str] = None
    edited_by: uuid.UUID
    created_at: datetime


class VariableInfo(BaseModel):
    key: str
    label: str


class ReportBucket(BaseModel):
    label: str
    count: int


class MostUsed(BaseModel):
    id: str
    name: str
    channel: str
    usage_count: int


class TemplateReportResponse(BaseModel):
    total: int
    total_usage: int
    pending_approval: int
    approved: int
    drafts: int
    by_channel: List[ReportBucket]
    by_status: List[ReportBucket]
    by_category: List[ReportBucket]
    most_used: List[MostUsed]

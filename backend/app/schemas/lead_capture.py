import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LeadCaptureSourceCreate(BaseModel):
    name: str = Field(..., max_length=120)
    provider: str = Field("generic", max_length=30)  # generic|meta_lead_ads|google_ads|web_form|zapier
    source_label: str = Field("Web Lead", max_length=100)
    default_pipeline_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None  # defaults to the creating admin
    secret: str | None = Field(None, max_length=128)         # HMAC secret for signature verification
    meta_verify_token: str | None = Field(None, max_length=64)
    field_mapping: dict | None = None                        # {incoming_key: lead_field}


class LeadCaptureSourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    source_label: str | None = Field(None, max_length=100)
    default_pipeline_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    secret: str | None = Field(None, max_length=128)
    meta_verify_token: str | None = Field(None, max_length=64)
    field_mapping: dict | None = None
    is_active: bool | None = None


class LeadCaptureSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    provider: str
    token: str
    source_label: str
    default_pipeline_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID
    field_mapping: dict | None = None
    is_active: bool
    leads_captured: int
    last_received_at: datetime | None = None
    has_secret: bool = False
    webhook_url: str | None = None
    created_at: datetime


class LeadCaptureEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    external_id: str | None = None
    lead_id: uuid.UUID | None = None
    status: str
    error: str | None = None
    created_at: datetime

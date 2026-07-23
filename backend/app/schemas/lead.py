import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, SerializationInfo

class LeadBase(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    company_name: str | None = Field(None, max_length=255)
    title: str = Field(..., max_length=255)
    status: str = Field("New", max_length=50)
    source: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    value: Decimal | None = None
    priority: str = Field("Medium", max_length=20)
    assigned_user_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    pin_code: str | None = Field(None, max_length=20)
    branch_id: uuid.UUID | None = None
    territory_id: uuid.UUID | None = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    company_name: str | None = Field(None, max_length=255)
    title: str | None = Field(None, max_length=255)
    status: str | None = Field(None, max_length=50)
    lost_reason: str | None = Field(None, max_length=150)
    source: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    value: Decimal | None = None
    priority: str | None = Field(None, max_length=20)
    assigned_user_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    pin_code: str | None = Field(None, max_length=20)
    branch_id: uuid.UUID | None = None
    territory_id: uuid.UUID | None = None

class LeadTimelineEvent(BaseModel):
    type: str  # "note" | "activity" | "audit"
    id: str
    timestamp: datetime
    title: str
    description: str | None = None
    actor_user_id: str | None = None
    event_metadata: dict | None = None


class LeadAuditEvent(BaseModel):
    id: str
    action: str
    actor_user_id: str | None = None
    created_at: datetime
    action_metadata: dict | None = None


class LeadAttachmentResponse(BaseModel):
    filename: str
    url: str
    size: int | None = None
    uploaded_by: str | None = None
    uploaded_at: str | None = None


class LeadConvertRequest(BaseModel):
    create_company: bool = True


class LeadConvertResponse(BaseModel):
    contact_id: uuid.UUID
    company_id: uuid.UUID | None = None
    lead_id: uuid.UUID


class LeadReminderCreate(BaseModel):
    remind_at: datetime
    note: str | None = None
    user_id: uuid.UUID | None = None


class LeadReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    user_id: uuid.UUID
    remind_at: datetime
    note: str | None = None
    is_sent: bool
    created_at: datetime


class LeadBulkUpdateFields(BaseModel):
    """Allowlisted fields that may be set in a bulk update."""
    status: str | None = Field(None, max_length=50)
    stage_id: uuid.UUID | None = None
    priority: str | None = Field(None, max_length=20)
    source: str | None = Field(None, max_length=100)
    assigned_user_id: uuid.UUID | None = None

class LeadBulkUpdateRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(..., min_length=1)
    fields: LeadBulkUpdateFields

class LeadBulkUpdateResponse(BaseModel):
    updated_count: int
    lead_ids: list[uuid.UUID]

from app.schemas.pipeline import PipelineStageResponse

class LeadResponse(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    score: int = 0
    is_archived: bool = False
    archived_at: datetime | None = None
    attachments: list | None = None
    converted_contact_id: uuid.UUID | None = None
    converted_at: datetime | None = None
    lost_reason: str | None = None
    company_id: uuid.UUID | None = None
    stage: PipelineStageResponse | None = None

    @field_serializer("phone")
    def serialize_phone(self, phone: str | None, info: SerializationInfo) -> str | None:
        if not phone:
            return phone
        
        from app.core.context import mask_phone_ctx
        if mask_phone_ctx.get():
            phone_clean = phone.strip()
            if phone_clean.startswith("+"):
                if len(phone_clean) <= 5:
                    return "+" + "*" * (len(phone_clean) - 1)
                return phone_clean[:3] + "*" * (len(phone_clean) - 5) + phone_clean[-2:]
            else:
                if len(phone_clean) <= 4:
                    return "*" * len(phone_clean)
                return phone_clean[:2] + "*" * (len(phone_clean) - 4) + phone_clean[-2:]
        return phone


class FollowUpCreate(BaseModel):
    """One-shot follow-up capture: the outcome of this touch + the next one."""
    outcome: str = Field("Follow-up", max_length=40)
    remarks: str | None = None
    follow_up_type: str = Field("call", max_length=20)  # call|whatsapp|email|meeting|site_visit|visit|other
    next_follow_up_at: datetime | None = None
    priority: str = Field("Medium", max_length=20)      # Low|Medium|High|Urgent
    reminder_minutes_before: int | None = Field(None, ge=0, le=10080)
    create_calendar_event: bool = False
    set_status: str | None = Field(None, max_length=50)

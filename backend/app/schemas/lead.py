import uuid
from typing import Any
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
    custom_fields: dict[str, Any] | None = None

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
    custom_fields: dict[str, Any] | None = None

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

    @field_serializer("custom_fields")
    def serialize_custom_fields(self, custom_fields: dict[str, Any] | None, info: SerializationInfo) -> dict[str, Any] | None:
        if not custom_fields:
            return custom_fields
        
        from app.core.context import mask_phone_ctx
        if mask_phone_ctx.get():
            masked = dict(custom_fields)
            for key, val in masked.items():
                if isinstance(val, str) and ("phone" in key.lower() or "mobile" in key.lower()):
                    phone_clean = val.strip()
                    if phone_clean.startswith("+"):
                        if len(phone_clean) <= 5:
                            masked[key] = "+" + "*" * (len(phone_clean) - 1)
                        else:
                            masked[key] = phone_clean[:3] + "*" * (len(phone_clean) - 5) + phone_clean[-2:]
                    else:
                        if len(phone_clean) <= 4:
                            masked[key] = "*" * len(phone_clean)
                        else:
                            masked[key] = phone_clean[:2] + "*" * (len(phone_clean) - 4) + phone_clean[-2:]
            return masked
        return custom_fields


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


# --- Enterprise High-Performance Aggregations (Million-Lead Scale) ---

class SalesKPISummaryResponse(BaseModel):
    """Database-side aggregate of 5 core Sales KPIs computed in a single SQL query."""
    active_pipeline_value: Decimal = Decimal("0")
    active_deals_count: int = 0
    weighted_forecast: Decimal = Decimal("0")
    won_revenue_this_month: Decimal = Decimal("0")
    won_deals_count: int = 0
    lost_deals_count: int = 0
    win_rate: float = 0.0
    overdue_followups_count: int = 0
    total_leads_count: int = 0


class KanbanStageSummary(BaseModel):
    """Accurate server-calculated totals for a single pipeline stage + initial cards."""
    stage_id: uuid.UUID
    stage_name: str
    order_position: int = 0
    total_count: int = 0
    total_value: Decimal = Decimal("0")
    cards: list[LeadResponse] = []
    has_more: bool = False


class KanbanBoardResponse(BaseModel):
    """Enterprise Kanban board response with stage aggregates and initial cards."""
    pipeline_id: uuid.UUID | None = None
    stages: list[KanbanStageSummary] = []
    total_pipeline_value: Decimal = Decimal("0")
    total_deals_count: int = 0


class KanbanStageCardsResponse(BaseModel):
    """Paginated cards for a single Kanban stage (incremental loading)."""
    stage_id: uuid.UUID
    total_count: int = 0
    cards: list[LeadResponse] = []
    has_more: bool = False
    skip: int = 0
    limit: int = 10


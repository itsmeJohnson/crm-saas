import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class CompanyBase(BaseModel):
    name: str = Field(..., max_length=255)
    domain: str | None = Field(None, max_length=255)
    industry: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    assigned_user_id: uuid.UUID | None = None
    company_type: str = Field("Prospect", max_length=30)
    source: str | None = Field(None, max_length=100)
    employee_count: int | None = None
    annual_revenue: Decimal | None = None
    tags: list[str] | None = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    domain: str | None = Field(None, max_length=255)
    industry: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    assigned_user_id: uuid.UUID | None = None
    company_type: str | None = Field(None, max_length=30)
    source: str | None = Field(None, max_length=100)
    employee_count: int | None = None
    annual_revenue: Decimal | None = None
    tags: list[str] | None = None

class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    attachments: list | None = None


# --- Associations ---
class CompanyContactSummary(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    job_title: str | None = None

class CompanyLeadSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    stage: str | None = None
    value: Decimal | None = None
    assigned_user_id: uuid.UUID | None = None

class CompanyDealsSummary(BaseModel):
    total_leads: int
    open_count: int
    won_count: int          # converted (== associated customers)
    lost_count: int
    total_value: float
    won_value: float
    by_stage: list[dict]


# --- Timeline / communications ---
class CompanyTimelineEvent(BaseModel):
    type: str
    id: str
    timestamp: datetime
    title: str
    description: str | None = None
    actor_user_id: str | None = None
    event_metadata: dict | None = None

class CompanyCommunication(BaseModel):
    id: str
    channel: str
    subject: str
    description: str | None = None
    direction: str | None = None
    status: str
    timestamp: datetime
    recording_url: str | None = None


# --- Attachments ---
class CompanyAttachmentResponse(BaseModel):
    filename: str
    url: str
    size: int | None = None
    uploaded_by: str | None = None
    uploaded_at: str | None = None


# --- Reports ---
class CompanyReportBucket(BaseModel):
    label: str
    count: int
    revenue: float

class CompanyReportResponse(BaseModel):
    total_companies: int
    total_revenue: float
    total_employees: int
    customers: int
    prospects: int
    partners: int
    by_industry: list[CompanyReportBucket]
    by_type: list[CompanyReportBucket]
    by_source: list[CompanyReportBucket]
    top_by_revenue: list[dict]

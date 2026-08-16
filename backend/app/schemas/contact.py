import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ContactBase(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    job_title: str | None = Field(None, max_length=100)
    company_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None

class ContactCreate(ContactBase):
    # Reject creating a patient whose phone/email already exists; set true to override
    # (e.g. family members who legitimately share a contact number).
    allow_duplicate: bool = False

class ContactUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    job_title: str | None = Field(None, max_length=100)
    company_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None

class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    attachments: list | None = None


# --- Bulk actions ---
class ContactBulkUpdateFields(BaseModel):
    company_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    add_tags: list[str] | None = None
    remove_tags: list[str] | None = None

class ContactBulkUpdateRequest(BaseModel):
    contact_ids: list[uuid.UUID] = Field(..., min_length=1)
    fields: ContactBulkUpdateFields

class ContactBulkDeleteRequest(BaseModel):
    contact_ids: list[uuid.UUID] = Field(..., min_length=1)

class ContactBulkResult(BaseModel):
    affected_count: int
    contact_ids: list[uuid.UUID]


# --- Timeline / communications ---
class ContactTimelineEvent(BaseModel):
    type: str  # note | activity | audit
    id: str
    timestamp: datetime
    title: str
    description: str | None = None
    actor_user_id: str | None = None
    event_metadata: dict | None = None

class ContactCommunication(BaseModel):
    id: str
    channel: str  # Call | Email
    subject: str
    description: str | None = None
    direction: str | None = None
    status: str
    timestamp: datetime
    recording_url: str | None = None


# --- Attachments ---
class ContactAttachmentResponse(BaseModel):
    filename: str
    url: str
    size: int | None = None
    uploaded_by: str | None = None
    uploaded_at: str | None = None


# --- Merge ---
class ContactMergeRequest(BaseModel):
    primary_id: uuid.UUID
    secondary_id: uuid.UUID


# --- Relationships ---
class ContactRelationshipCreate(BaseModel):
    related_contact_id: uuid.UUID
    relationship_type: str = Field(..., max_length=50)

class ContactRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    related_contact_id: uuid.UUID
    relationship_type: str
    related_contact_name: str | None = None


# --- Custom field definitions ---
class CustomFieldDefinitionCreate(BaseModel):
    key: str = Field(..., max_length=80, pattern=r"^[a-zA-Z0-9_]+$")
    label: str = Field(..., max_length=150)
    field_type: str = Field("text", max_length=30)
    options: list[str] | None = None

class CustomFieldDefinitionUpdate(BaseModel):
    label: str | None = Field(None, max_length=150)
    field_type: str | None = Field(None, max_length=30)
    options: list[str] | None = None
    is_active: bool | None = None

class CustomFieldDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: str
    key: str
    label: str
    field_type: str
    options: list[str] | None = None
    is_active: bool


# --- Reports ---
class ContactReportBucket(BaseModel):
    label: str
    count: int

class ContactReportResponse(BaseModel):
    total_contacts: int
    with_email: int
    with_phone: int
    with_company: int
    by_company: list[ContactReportBucket]
    by_owner: list[ContactReportBucket]
    by_tag: list[ContactReportBucket]

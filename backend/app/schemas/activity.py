import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ActivityBase(BaseModel):
    activity_type: str = Field(..., max_length=50) # e.g. Call, Meeting, Email, Task
    subject: str = Field(..., max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    status: str = Field("Planned", max_length=50) # e.g. Planned, Completed, Overdue
    assigned_user_id: uuid.UUID | None = None
    
    # Optional references
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None

class ActivityCreate(ActivityBase):
    pass

class ActivityUpdate(BaseModel):
    activity_type: str | None = Field(None, max_length=50)
    subject: str | None = Field(None, max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    status: str | None = Field(None, max_length=50)
    assigned_user_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None

class ActivityResponse(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

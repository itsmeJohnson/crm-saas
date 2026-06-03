import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class LeadBase(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    company_name: str | None = Field(None, max_length=255)
    title: str = Field(..., max_length=255)
    status: str = Field("New", max_length=50)
    source: str | None = Field(None, max_length=100)
    value: Decimal | None = None
    assigned_user_id: uuid.UUID | None = None

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
    source: str | None = Field(None, max_length=100)
    value: Decimal | None = None
    assigned_user_id: uuid.UUID | None = None

class LeadResponse(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

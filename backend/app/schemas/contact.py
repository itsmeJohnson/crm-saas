import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ContactBase(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    job_title: str | None = Field(None, max_length=100)
    company_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    job_title: str | None = Field(None, max_length=100)
    company_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None

class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

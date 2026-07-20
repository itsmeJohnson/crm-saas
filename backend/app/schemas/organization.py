import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    is_active: bool | None = None

class OrganizationResponse(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    subscription_plan: str | None = None
    subscription_status: str | None = None
    subscription_expires_at: datetime | None = None
    max_users: int | None = None
    created_at: datetime
    updated_at: datetime

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
    created_at: datetime
    updated_at: datetime

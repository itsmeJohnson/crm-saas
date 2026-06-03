import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    role: str = "User"

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    organization_id: uuid.UUID

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    role: str | None = Field(None, pattern="^(OrgAdmin|Manager|Employee)$")

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    is_verified: bool
    is_invited: bool
    created_at: datetime
    updated_at: datetime

import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class InvitationBase(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern="^(OrgAdmin|Manager|Employee)$")

class InvitationCreate(InvitationBase):
    pass

class InvitationResponse(InvitationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    token: str
    expires_at: datetime
    accepted: bool
    revoked: bool
    created_by: uuid.UUID
    created_at: datetime

class InvitationAccept(BaseModel):
    token: str
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class TrialRequestCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    company_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=50)

class TrialRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    company_name: str
    email: str
    phone: str
    status: str
    created_at: datetime
    updated_at: datetime

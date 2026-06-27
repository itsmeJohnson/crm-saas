import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    role: str = "Employee"
    reporting_to_id: uuid.UUID | None = None
    phone: str | None = Field(None, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    role: str | None = Field(None, pattern="^(OrgAdmin|Manager|Employee)$")
    reporting_to_id: uuid.UUID | None = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    is_verified: bool
    is_invited: bool
    created_at: datetime
    updated_at: datetime
    is_team_leader: bool = False
    seat_number: str | None = None
    inactive_reason: str | None = None
    mfa_enabled: bool = False

class ReplaceEmployeeRequest(BaseModel):
    old_user_id: uuid.UUID
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    reporting_to_id: uuid.UUID | None = None
    password: str = Field(..., min_length=8)
    role: str = "Employee"
    phone: str | None = Field(None, max_length=50)

class SeatUtilizationResponse(BaseModel):
    licensed_seats: int
    active_users: int
    inactive_assigned_seats: int
    available_new_seats: int
    replace_employee_available: int

class SeatHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seat_number: str
    user_id: uuid.UUID | None
    user_name: str | None
    action: str
    created_at: datetime
    performed_by_name: str | None
    remarks: str | None

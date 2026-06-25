from pydantic import BaseModel, EmailStr, Field
from app.schemas.organization import OrganizationResponse
from app.schemas.user import UserResponse

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterTenantRequest(BaseModel):
    company_name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    licensed_seats: int = Field(10, ge=10, description="Number of purchased user licenses, minimum 10.")
    contract_months: int = Field(3, ge=3, description="Contract length in months, minimum 3.")

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AuthMeResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse
    features: list[str] = []

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="The password reset token")
    password: str = Field(..., min_length=8, description="The new password")

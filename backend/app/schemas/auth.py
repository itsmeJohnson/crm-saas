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
    plan_name: str | None = None
    billing_cycle: str = "monthly"
    is_trial: bool = False

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # MFA challenge: when mfa_required=True, access_token is a short-lived mfa_token
    # and refresh_token is empty. Frontend must call /auth/mfa/verify to get real tokens.
    mfa_required: bool = False

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

# ---------- MFA Schemas ----------

class MFAVerifyRequest(BaseModel):
    """Used for: login MFA challenge, enable confirmation, disable"""
    totp_code: str | None = Field(None, description="6-digit TOTP code from authenticator app")
    backup_code: str | None = Field(None, description="8-character backup code")
    mfa_token: str | None = Field(None, description="Short-lived token from login response when mfa_required=True")

class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str
    issuer: str
    message: str

class MFAEnableResponse(BaseModel):
    message: str
    backup_codes: list[str]
    warning: str

class MFAStatusResponse(BaseModel):
    mfa_enabled: bool
    backup_codes_remaining: int

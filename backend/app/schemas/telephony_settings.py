from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class TelephonyConfigResponse(BaseModel):
    """Organization telephony config as returned to authorised admins.

    NEVER contains a secret value. Each secret is represented by a boolean
    ``has_*`` flag so the UI can show "configured" without ever receiving the
    credential (plaintext or ciphertext).
    """
    model_config = ConfigDict(from_attributes=True)

    provider: str
    is_active: bool
    is_connected: bool

    company_id: Optional[str] = None
    public_ivr_id: Optional[str] = None
    call_type: str = "1"
    user_uuid: Optional[str] = None
    default_caller_id: Optional[str] = None
    std_code: Optional[str] = None
    webhook_url: Optional[str] = None

    # Secret presence flags — never the values.
    has_authentication_token: bool = False
    has_x_api_key: bool = False
    has_secret_token: bool = False
    has_webhook_secret: bool = False

    call_recording: bool = True
    power_dialer: bool = False
    predictive_dialer: bool = False
    auto_assignment: bool = False

    call_retry_count: int = 4
    retry_interval_seconds: int = 7200
    max_call_duration_seconds: int = 3600


class TelephonyConfigUpdate(BaseModel):
    """Write-only update. All fields optional; a blank/None secret leaves the
    stored value unchanged (so the UI never has to re-send credentials)."""
    provider: Optional[str] = Field(default=None, pattern="^(myoperator|knowlarity)$")
    is_active: Optional[bool] = None

    company_id: Optional[str] = None
    public_ivr_id: Optional[str] = None
    call_type: Optional[str] = Field(default=None, pattern="^(1|2|3)$")
    user_uuid: Optional[str] = None
    default_caller_id: Optional[str] = None
    std_code: Optional[str] = None
    webhook_url: Optional[str] = None

    # Secrets — plaintext in, encrypted at rest, never echoed back.
    authentication_token: Optional[str] = None
    x_api_key: Optional[str] = None
    secret_token: Optional[str] = None
    webhook_secret: Optional[str] = None

    call_recording: Optional[bool] = None
    power_dialer: Optional[bool] = None
    predictive_dialer: Optional[bool] = None
    auto_assignment: Optional[bool] = None

    call_retry_count: Optional[int] = Field(default=None, ge=0, le=20)
    retry_interval_seconds: Optional[int] = Field(default=None, ge=0)
    max_call_duration_seconds: Optional[int] = Field(default=None, ge=0)

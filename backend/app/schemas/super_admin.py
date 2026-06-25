import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator, Field


class SubscriptionUpdateRequest(BaseModel):
    subscription_plan: str
    subscription_expires_at: datetime | None = None
    subscription_status: str
    max_users: int

class TenantUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    role: str
    is_active: bool

class TenantInvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    amount: float
    status: str
    due_date: datetime
    created_at: datetime

class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    subscription_plan: str
    subscription_expires_at: datetime | None = None
    subscription_status: str
    max_users: int
    user_count: int
    invoice_count: int

class InvoiceCreateRequest(BaseModel):
    amount: float
    due_date: datetime
    status: str = "Pending"

class PlanCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    monthly_price: float = 0.0
    quarterly_price: float = 0.0
    annual_price: float = 0.0
    currency: str = "INR"
    max_users: int = 50
    # Obsolete role limits (DEPRECATED, defaulted for backward compatibility)
    max_admins: int = 100
    max_managers: int = 100
    max_team_leads: int = 100
    max_employees: int = 100
    storage_limit_gb: int = 10
    recording_retention_days: int = 30
    priority_support: bool = False
    api_access: bool = False
    display_order: int = 0
    setup_charges: float = 0.0
    minimum_users: int = Field(10, ge=10, description="Minimum Initial Licensed Seats (default 10)")
    maximum_users: int = 1000
    minimum_contract_months: int = Field(3, ge=3, description="Minimum Initial Contract (default 3 months)")
    trial_days: int = 0
    extra_user_price: float = 0.0
    discount_percentage: float = 0.0
    gst_percentage: float = 0.0
    plan_color: str | None = None
    plan_badge: str | None = None
    popular_plan: bool = False
    recommended_plan: bool = False
    allow_upgrade: bool = True
    allow_downgrade: bool = True
    allow_trial: bool = True
    allow_additional_seats: bool = True
    auto_renew: bool = True
    plan_active: bool = True

    @field_validator("trial_days")
    @classmethod
    def validate_trial_days(cls, v: int) -> int:
        if v < 0 or v > 365:
            raise ValueError("Trial days must be between 0 and 365")
        return v

    @field_validator("discount_percentage")
    @classmethod
    def validate_discount(cls, v: float) -> float:
        if v < 0.0 or v > 100.0:
            raise ValueError("Discount must be between 0% and 100%")
        return v

    @field_validator("gst_percentage")
    @classmethod
    def validate_gst(cls, v: float) -> float:
        if v < 0.0 or v > 100.0:
            raise ValueError("GST must be between 0% and 100%")
        return v

    @field_validator("extra_user_price")
    @classmethod
    def validate_extra_user_price(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("Extra user price must be greater than or equal to zero")
        return v

class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    monthly_price: float
    quarterly_price: float
    annual_price: float
    currency: str
    max_users: int
    max_admins: int
    max_managers: int
    max_team_leads: int
    max_employees: int
    storage_limit_gb: int
    recording_retention_days: int
    priority_support: bool
    api_access: bool
    display_order: int
    setup_charges: float
    minimum_users: int
    maximum_users: int
    minimum_contract_months: int
    is_active: bool
    trial_days: int | None = None
    extra_user_price: float
    discount_percentage: float
    gst_percentage: float
    plan_color: str | None = None
    plan_badge: str | None = None
    popular_plan: bool
    recommended_plan: bool
    allow_upgrade: bool
    allow_downgrade: bool
    allow_trial: bool
    allow_additional_seats: bool
    auto_renew: bool
    plan_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FeatureResponse(BaseModel):
    id: uuid.UUID
    code: str
    display_name: str
    description: str | None = None
    category: str
    icon: str | None = None
    active: bool

    class Config:
        from_attributes = True

class PlanFeatureResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    feature_id: uuid.UUID
    enabled: bool
    feature: FeatureResponse | None = None

    class Config:
        from_attributes = True

class PlanFeatureToggle(BaseModel):
    plan_id: uuid.UUID
    feature_id: uuid.UUID
    enabled: bool

class PlanFeatureClone(BaseModel):
    from_plan_id: uuid.UUID
    to_plan_id: uuid.UUID

class SystemSettingRequest(BaseModel):
    key: str
    value: dict | list | str | int | float | bool | None = None

class SystemSettingResponse(BaseModel):
    key: str
    value: dict | list | str | int | float | bool | None = None


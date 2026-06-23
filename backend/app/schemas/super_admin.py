import uuid
from datetime import datetime
from pydantic import BaseModel

class SubscriptionUpdateRequest(BaseModel):
    subscription_plan: str
    subscription_expires_at: datetime | None = None
    subscription_status: str
    max_users: int

class TenantUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
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
    subscription_expires_at: datetime | None
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
    max_admins: int = 1
    max_managers: int = 2
    max_team_leads: int = 5
    max_employees: int = 42
    storage_limit_gb: int = 10
    recording_retention_days: int = 30
    priority_support: bool = False
    api_access: bool = False
    display_order: int = 0
    setup_charges: float = 0.0
    minimum_users: int = 1
    maximum_users: int = 1000
    minimum_contract_months: int = 1

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


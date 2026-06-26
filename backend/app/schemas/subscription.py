import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str | None = None
    description: str | None = None
    price_inr: float
    billing_cycle_days: int
    monthly_price: float | None = None
    quarterly_price: float | None = None
    annual_price: float | None = None
    max_users: int
    max_admins: int
    max_managers: int
    max_team_leads: int
    max_employees: int
    minimum_users: int | None = None
    maximum_users: int | None = None
    storage_limit_gb: int | None = None
    recording_retention_days: int | None = None
    setup_charges: float | None = None
    extra_user_price: float | None = None
    gst_percentage: float | None = None
    discount_percentage: float | None = None
    allow_additional_seats: bool | None = None
    popular_plan: bool | None = None
    recommended_plan: bool | None = None
    plan_badge: str | None = None
    plan_color: str | None = None
    plan_active: bool | None = None
    features: dict
    is_trial: bool
    trial_days: int | None = None
    is_active: bool

class TenantSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    start_date: datetime
    end_date: datetime
    trial_end_date: datetime | None = None
    auto_renew: bool
    billing_cycle: str | None = None
    users_purchased: int
    users_purchased_next: int | None = None
    users_active: int
    plan: PlanResponse | None = None

class UsageMeter(BaseModel):
    current: int
    limit: int
    percent: float

class SubscriptionDetailsResponse(BaseModel):
    subscription: TenantSubscriptionResponse | None = None
    usage: dict[str, UsageMeter]

class SubscriptionRenewResponse(BaseModel):
    success: bool
    message: str
    new_end_date: datetime

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    amount: float
    amount_inr: float | None = None
    currency: str
    status: str
    payment_status: str
    due_date: datetime
    issue_date: datetime
    plan_name: str | None = None

class ReduceSeatsRequest(BaseModel):
    new_seat_count: int = Field(..., ge=10, description="The new total seat count, must be at least 10.")

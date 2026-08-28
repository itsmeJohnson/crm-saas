import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price_inr: float
    billing_cycle_days: int
    max_users: int
    max_admins: int
    max_managers: int
    max_team_leads: int
    max_employees: int
    features: dict
    is_trial: bool
    trial_days: int | None = None
    is_active: bool
    extra_user_price: float = 0.0
    gst_percentage: float = 0.0

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
    billing_cycle: str
    users_purchased: int
    users_purchased_next: int | None = None
    users_active: int
    plan: PlanResponse
    pending_plan_id: uuid.UUID | None = None
    pending_billing_cycle: str | None = None
    pending_plan: PlanResponse | None = None

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
    new_seat_count: int = Field(..., ge=3, description="The new total seat count, must be at least 3.")

class ScheduledPlanChangeResponse(BaseModel):
    scheduled: bool = True
    plan_id: uuid.UUID
    plan_name: str
    billing_cycle: str
    effective_date: datetime
    message: str

class UpgradeSubscriptionResult(BaseModel):
    """Exactly one of the two fields is populated: an immediately-payable invoice,
    or a scheduled tier change (no payment due until it applies at renewal)."""
    invoice: InvoiceResponse | None = None
    scheduled_change: ScheduledPlanChangeResponse | None = None

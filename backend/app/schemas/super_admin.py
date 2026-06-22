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

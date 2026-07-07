import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class OrgProfileUpdate(BaseModel):
    website: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    timezone: str = Field("Asia/Kolkata", min_length=2)
    language: str = Field("English", min_length=2)
    currency: str = Field("INR", min_length=2)

class OrgBillingUpdate(BaseModel):
    billing_name: Optional[str] = None
    gst_number: Optional[str] = None
    pan: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_country: Optional[str] = None
    billing_pin_code: Optional[str] = None
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None

class OrgNotificationSettingsUpdate(BaseModel):
    notification_invoice_emails: bool
    notification_renewal_emails: bool
    notification_support_emails: bool
    auto_renewal: bool = True
    theme: str = Field("dark", pattern="^(light|dark)$")

class PurchaseSeatsRequest(BaseModel):
    user_count: int = Field(..., ge=1, le=500)
    billing_cycle: str = Field("monthly", pattern="^(monthly|quarterly|annual)$")
    gateway: str = Field("UPI", pattern="^(UPI|Stripe|Razorpay|Cashfree|PhonePe|Bank)$")

class PurchaseStorageRequest(BaseModel):
    storage_gb: int = Field(..., ge=1)
    gateway: str = Field("UPI", pattern="^(UPI|Stripe|Razorpay|Cashfree|PhonePe|Bank)$")

class PayInvoiceRequest(BaseModel):
    gateway: str = Field("UPI", pattern="^(UPI|Stripe|Razorpay|Cashfree|PhonePe|Bank)$")
    transaction_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_signature: Optional[str] = None

class SeatUsageMeter(BaseModel):
    current: int
    limit: int
    percent: float

class StorageUsageMeter(BaseModel):
    used_gb: float
    limit_gb: int
    percent: float

class DashboardStatsResponse(BaseModel):
    plan_name: str
    subscription_status: str
    days_remaining: int
    users: SeatUsageMeter
    storage: StorageUsageMeter
    recording_count: int
    pending_invoice_amount: float
    last_payment_amount: float
    upcoming_renewal_date: Optional[datetime] = None
    recent_activities: List[dict] = []

class UpgradeSubscriptionRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str = Field("monthly", pattern="^(monthly|quarterly|annual)$")
    gateway: str = Field("UPI", pattern="^(UPI|Stripe|Razorpay|Cashfree|PhonePe|Bank)$")


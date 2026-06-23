from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class CommercialSettingsBase(BaseModel):
    default_currency: str = Field(default="INR")
    currency_symbol: str = Field(default="₹")
    default_timezone: str = Field(default="Asia/Kolkata")
    
    default_gst: float = Field(default=18.0)
    gst_inclusive: bool = Field(default=False)
    tax_label: str = Field(default="GST")
    
    default_trial_days: int = Field(default=14)
    allow_trial: bool = Field(default=True)
    trial_reminder_days: int = Field(default=3)
    
    default_min_contract: int = Field(default=3)
    auto_renewal: bool = Field(default=True)
    notice_period_days: int = Field(default=15)
    
    default_setup_charge: float = Field(default=0.0)
    allow_setup_discount: bool = Field(default=True)
    free_setup_on_annual: bool = Field(default=True)
    
    default_extra_user_price: float = Field(default=0.0)
    minimum_users: int = Field(default=10)
    maximum_users: Optional[int] = None
    
    default_discount_percentage: float = Field(default=0.0)
    maximum_discount_percentage: float = Field(default=25.0)
    allow_custom_discount: bool = Field(default=True)
    allow_promo_code: bool = Field(default=True)
    
    late_payment_charge: float = Field(default=0.0)
    late_payment_type: str = Field(default="flat")
    grace_period_days: int = Field(default=7)
    auto_suspend_days: int = Field(default=30)
    auto_reactivate: bool = Field(default=True)
    
    reminder_schedule: str = Field(default="{}")
    invoice_reminder_days: str = Field(default="7,3,1")
    subscription_reminder_days: str = Field(default="15,7,3,0")
    payment_reminder_days: str = Field(default="0,3,7,15")
    
    default_plan_id: Optional[str] = None
    default_recording_retention_days: int = Field(default=90)
    default_storage_gb: int = Field(default=50)
    
    invoice_reminder_template: Optional[str] = None
    renewal_reminder_template: Optional[str] = None
    trial_expiry_template: Optional[str] = None
    payment_success_template: Optional[str] = None
    payment_failed_template: Optional[str] = None
    welcome_template: Optional[str] = None

class CommercialSettingsUpdate(CommercialSettingsBase):
    reason: Optional[str] = Field(None, description="Reason for updating settings, for audit logs")

    @field_validator("default_gst", "default_discount_percentage", "maximum_discount_percentage")
    @classmethod
    def validate_percentages(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Percentage value cannot be negative")
        return v

    @field_validator("minimum_users")
    @classmethod
    def validate_min_users(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Minimum users must be at least 1")
        return v

    @field_validator(
        "default_trial_days", 
        "trial_reminder_days", 
        "default_min_contract", 
        "notice_period_days", 
        "grace_period_days", 
        "auto_suspend_days", 
        "default_recording_retention_days", 
        "default_storage_gb"
    )
    @classmethod
    def validate_non_negative_ints(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v

class CommercialSettingsResponse(CommercialSettingsBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

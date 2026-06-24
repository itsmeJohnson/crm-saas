from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class InvoiceConfigBase(BaseModel):
    company_name: str = Field(default="Johnson Softwares")
    tagline: str | None = None
    website: str | None = None
    support_email: str | None = None
    phone_number: str | None = None
    address: str | None = None

    gst_number: str | None = None
    pan: str | None = None
    business_registration_number: str | None = None

    invoice_prefix: str = Field(default="INV-2026")
    starting_invoice_number: int = Field(default=1001)
    currency: str = Field(default="INR")
    currency_symbol: str = Field(default="₹")

    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc: str | None = None
    branch: str | None = None
    upi_id: str | None = None

    payment_terms: str | None = None
    footer_text: str | None = None

    invoice_subject: str | None = None
    invoice_body: str | None = None
    reminder_subject: str | None = None
    reminder_body: str | None = None
    payment_success_subject: str | None = None
    payment_success_body: str | None = None
    payment_failed_subject: str | None = None
    payment_failed_body: str | None = None
    renewal_reminder_subject: str | None = None
    renewal_reminder_body: str | None = None

    @field_validator("starting_invoice_number")
    @classmethod
    def validate_starting_invoice_number(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Starting invoice number must be at least 1")
        return v

class InvoiceConfigUpdate(InvoiceConfigBase):
    pass

class InvoiceConfigResponse(InvoiceConfigBase):
    company_logo_url: str | None = None
    qr_code_url: str | None = None
    updated_at: datetime

    class Config:
        from_attributes = True

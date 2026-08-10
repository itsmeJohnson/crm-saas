import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class OrgInvoiceSettingsUpdate(BaseModel):
    legal_name: str | None = Field(None, max_length=200)
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=255)
    logo_url: str | None = None
    gst_number: str | None = Field(None, max_length=30)
    pan: str | None = Field(None, max_length=20)
    tax_label: str | None = Field(None, max_length=20)
    default_tax_percent: Decimal | None = Field(None, ge=0, le=100)
    currency: str | None = Field(None, max_length=10)
    currency_symbol: str | None = Field(None, max_length=6)
    invoice_prefix: str | None = Field(None, max_length=20)
    next_invoice_number: int | None = Field(None, ge=1)
    number_padding: int | None = Field(None, ge=0, le=10)
    bank_name: str | None = Field(None, max_length=120)
    account_holder: str | None = Field(None, max_length=120)
    account_number: str | None = Field(None, max_length=40)
    ifsc: str | None = Field(None, max_length=20)
    upi_id: str | None = Field(None, max_length=80)
    payment_terms: str | None = None
    footer_text: str | None = None
    default_notes: str | None = None


class OrgInvoiceSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    legal_name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_url: str | None = None
    gst_number: str | None = None
    pan: str | None = None
    tax_label: str
    default_tax_percent: Decimal
    currency: str
    currency_symbol: str
    invoice_prefix: str
    next_invoice_number: int
    number_padding: int
    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc: str | None = None
    upi_id: str | None = None
    payment_terms: str | None = None
    footer_text: str | None = None
    default_notes: str | None = None

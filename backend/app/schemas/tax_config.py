import uuid
from pydantic import BaseModel
from datetime import datetime


class TaxConfigCreate(BaseModel):
    country_code: str
    country_name: str
    tax_type: str = "GST"  # GST, VAT, SALES_TAX, NONE
    tax_rate: float = 0.0
    tax_label: str = "Tax"
    tax_inclusive: bool = False
    is_active: bool = True
    is_default: bool = False
    state_code: str | None = None


class TaxConfigUpdate(BaseModel):
    tax_rate: float | None = None
    tax_label: str | None = None
    tax_type: str | None = None
    tax_inclusive: bool | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class TaxConfigResponse(BaseModel):
    id: uuid.UUID
    country_code: str
    country_name: str
    tax_type: str
    tax_rate: float
    tax_label: str
    tax_inclusive: bool
    is_active: bool
    is_default: bool
    state_code: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

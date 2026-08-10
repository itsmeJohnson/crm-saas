import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


# --- Line items ---
class LineItem(BaseModel):
    description: str = Field(..., max_length=500)
    quantity: Decimal = Field(1, ge=0)
    unit_price: Decimal = Field(0, ge=0)
    amount: Decimal | None = None  # computed if omitted


# --- Orders ---
class OrderBase(BaseModel):
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    status: str = Field("Draft", max_length=30)
    currency: str = Field("USD", max_length=10)
    order_date: datetime | None = None
    items: list[LineItem] = []
    discount_amount: Decimal = Field(0, ge=0)
    tax_amount: Decimal = Field(0, ge=0)
    notes: str | None = None

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    status: str | None = Field(None, max_length=30)
    currency: str | None = Field(None, max_length=10)
    order_date: datetime | None = None
    items: list[LineItem] | None = None
    discount_amount: Decimal | None = Field(None, ge=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None

class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    order_number: str
    status: str
    currency: str
    order_date: datetime | None = None
    items: list = []
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Invoices ---
class InvoiceCreate(BaseModel):
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    currency: str = Field("USD", max_length=10)
    issue_date: datetime | None = None
    due_date: datetime | None = None
    items: list[LineItem] = []
    discount_amount: Decimal = Field(0, ge=0)
    tax_amount: Decimal = Field(0, ge=0)
    notes: str | None = None

class InvoiceFromOrderRequest(BaseModel):
    order_id: uuid.UUID
    due_date: datetime | None = None

class InvoiceUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    status: str | None = Field(None, max_length=30)
    currency: str | None = Field(None, max_length=10)
    issue_date: datetime | None = None
    due_date: datetime | None = None
    items: list[LineItem] | None = None
    discount_amount: Decimal | None = Field(None, ge=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    invoice_number: str
    status: str
    currency: str
    issue_date: datetime | None = None
    due_date: datetime | None = None
    items: list = []
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Payments ---
class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    method: str = Field("BankTransfer", max_length=30)
    reference: str | None = Field(None, max_length=120)
    paid_at: datetime | None = None
    notes: str | None = None
    # By default a payment cannot exceed the invoice's outstanding balance
    # (guards against negative balance_due / corrupted AR). Set true to
    # deliberately record an overpayment (e.g. an advance / credit on account).
    allow_overpayment: bool = False

class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    currency: str
    method: str
    reference: str | None = None
    paid_at: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Contracts ---
class ContractCreate(BaseModel):
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    title: str = Field(..., max_length=255)
    status: str = Field("Draft", max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    value: Decimal | None = None
    currency: str = Field("USD", max_length=10)
    renewal_terms: str | None = Field(None, max_length=255)
    document_url: str | None = Field(None, max_length=512)
    notes: str | None = None

class ContractUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    title: str | None = Field(None, max_length=255)
    status: str | None = Field(None, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    value: Decimal | None = None
    currency: str | None = Field(None, max_length=10)
    renewal_terms: str | None = Field(None, max_length=255)
    document_url: str | None = Field(None, max_length=512)
    notes: str | None = None

class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    contract_number: str
    title: str
    status: str
    start_date: date | None = None
    end_date: date | None = None
    value: Decimal | None = None
    currency: str
    renewal_terms: str | None = None
    document_url: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Customer 360 ---
class CustomerListItem(BaseModel):
    company_id: uuid.UUID
    name: str
    industry: str | None = None
    annual_revenue: Decimal | None = None
    order_count: int
    total_invoiced: float
    outstanding_balance: float

class CustomerSummary(BaseModel):
    company_id: uuid.UUID
    name: str
    company_type: str
    orders: dict
    invoices: dict
    payments: dict
    contracts: dict


# --- Unified timeline ---
class TimelineEvent(BaseModel):
    type: str
    id: str
    timestamp: datetime
    group: str
    title: str
    description: str | None = None
    actor_user_id: str | None = None
    actor_name: str | None = None
    source: str
    metadata: dict | None = None


# --- Reports ---
class CustomerReportResponse(BaseModel):
    total_customers: int
    total_orders: int
    total_order_value: float
    total_invoiced: float
    total_collected: float
    outstanding_ar: float
    overdue_ar: float
    active_contracts: int
    invoices_by_status: list[dict]
    top_customers: list[dict]

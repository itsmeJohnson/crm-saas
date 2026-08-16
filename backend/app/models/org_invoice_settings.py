import uuid
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class OrgInvoiceSettings(BaseModel):
    """Per-tenant invoicing configuration for a clinic's OWN patient/customer
    invoices (distinct from the platform's subscription InvoiceConfig).

    Controls the branding on generated invoices/receipts, the tax label &
    default rate, the currency, and the per-tenant invoice-number sequence.
    """
    __tablename__ = "org_invoice_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, unique=True, index=True)

    # --- Issuer / clinic identity (the "from" block on the invoice) ---
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # URL or data: URI

    # --- Tax / statutory ---
    gst_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_label: Mapped[str] = mapped_column(String(20), nullable=False, default="GST")
    default_tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))

    # --- Currency ---
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    currency_symbol: Mapped[str] = mapped_column(String(6), nullable=False, default="₹")

    # --- Numbering (per-tenant sequence) ---
    invoice_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="INV-")
    next_invoice_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    number_padding: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # --- Payment details shown on the invoice ---
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ifsc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    upi_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Copy ---
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

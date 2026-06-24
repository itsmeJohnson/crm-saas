from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class InvoiceConfig(Base):
    __tablename__ = "invoice_configurations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default="default")
    
    # Company Info
    company_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), default="Johnson Softwares", nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), default="www.johnsonsoftwares.com", nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(255), default="support@johnsonsoftwares.com", nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), default="+1-123-456-7890", nullable=True)
    address: Mapped[str | None] = mapped_column(Text, default="101, Antigravity Heights, Google DeepMind St, BKC, Mumbai - 400051", nullable=True)

    # Tax Info
    gst_number: Mapped[str | None] = mapped_column(String(50), default="27AAAAA1111A1Z1", nullable=True)
    pan: Mapped[str | None] = mapped_column(String(50), default="ABCDE1234F", nullable=True)
    business_registration_number: Mapped[str | None] = mapped_column(String(100), default="U12345MH2026PTC123456", nullable=True)

    # Invoice Settings
    invoice_prefix: Mapped[str] = mapped_column(String(50), default="INV-2026", nullable=False)
    starting_invoice_number: Mapped[int] = mapped_column(Integer, default=1001, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(10), default="₹", nullable=False)

    # Payment Settings
    bank_name: Mapped[str | None] = mapped_column(String(255), default="HDFC Bank", nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(255), default="Johnson Softwares Private Limited", nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(100), default="50100012345678", nullable=True)
    ifsc: Mapped[str | None] = mapped_column(String(50), default="HDFC0000123", nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), default="BKC Branch", nullable=True)
    upi_id: Mapped[str | None] = mapped_column(String(255), default="johnsonsoftwares@upi", nullable=True)
    qr_code_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Rich Text Terms & Footer
    payment_terms: Mapped[str | None] = mapped_column(Text, default="<p>Payment Due within 15 Days</p><p>Late Fee Applicable</p><p>Subscription Suspended after 30 Days</p>", nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, default="<p>Thank you for choosing Johnson Softwares.</p><p>This invoice is system generated.</p>", nullable=True)

    # Email Templates
    invoice_subject: Mapped[str | None] = mapped_column(String(255), default="Invoice {invoice_number} from Johnson Softwares", nullable=True)
    invoice_body: Mapped[str | None] = mapped_column(Text, default="Dear {customer_name},\n\nPlease find attached invoice {invoice_number} for your subscription.\n\nBest regards,\nJohnson Softwares", nullable=True)
    reminder_subject: Mapped[str | None] = mapped_column(String(255), default="Payment Reminder: Invoice {invoice_number}", nullable=True)
    reminder_body: Mapped[str | None] = mapped_column(Text, default="Dear {customer_name},\n\nThis is a friendly reminder that invoice {invoice_number} is due on {due_date}.\n\nBest regards,\nJohnson Softwares", nullable=True)
    payment_success_subject: Mapped[str | None] = mapped_column(String(255), default="Payment Received: Invoice {invoice_number}", nullable=True)
    payment_success_body: Mapped[str | None] = mapped_column(Text, default="Dear {customer_name},\n\nWe have received payment for invoice {invoice_number}. Thank you!\n\nBest regards,\nJohnson Softwares", nullable=True)
    payment_failed_subject: Mapped[str | None] = mapped_column(String(255), default="Payment Failed: Invoice {invoice_number}", nullable=True)
    payment_failed_body: Mapped[str | None] = mapped_column(Text, default="Dear {customer_name},\n\nWe attempted to charge your account for invoice {invoice_number}, but the payment failed.\n\nPlease update your payment details.\n\nBest regards,\nJohnson Softwares", nullable=True)
    renewal_reminder_subject: Mapped[str | None] = mapped_column(String(255), default="Your Subscription Renewal is Coming Up", nullable=True)
    renewal_reminder_body: Mapped[str | None] = mapped_column(Text, default="Dear {customer_name},\n\nYour subscription will renew on {renewal_date}.\n\nBest regards,\nJohnson Softwares", nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

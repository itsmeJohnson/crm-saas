import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.note import Note
from app.models.session import UserSession
from app.models.invitation import UserInvitation
from app.models.audit_log import AuditLog
from app.models.pipeline import PipelineStage
from app.models.target import PerformanceTarget
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.tenant_subscription import TenantSubscription
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.payment import Payment
from app.models.system_setting import SystemSetting
from app.models.invoice_config import InvoiceConfig
from app.models.commercial_settings import CommercialSettings
from app.repositories.organization import OrganizationRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_saas")

FEATURES = [
    # Leads
    {"code": "LEAD_MANAGEMENT", "display_name": "Lead Management", "category": "Leads", "icon": "Users", "description": "Manage leads, stages, follow-ups"},
    {"code": "BULK_ASSIGNMENT", "display_name": "Bulk Lead Assignment", "category": "Leads", "icon": "UserPlus", "description": "Assign multiple leads to agents at once"},
    {"code": "BULK_TRANSFER", "display_name": "Bulk Lead Transfer", "category": "Leads", "icon": "Move", "description": "Transfer batches of leads between agents"},
    {"code": "SMART_DISTRIBUTION", "display_name": "Smart Lead Distribution", "category": "Leads", "icon": "Shuffle", "description": "Automatically distribute leads using routing strategies"},
    {"code": "GOOGLE_SHEETS_IMPORT", "display_name": "Google Sheets Import", "category": "Leads", "icon": "FileSpreadsheet", "description": "Import leads directly from Google Sheets"},
    
    # Calls
    {"code": "CLICK_TO_CALL", "display_name": "Click-to-Call", "category": "Calls", "icon": "PhoneCall", "description": "Initiate dialer calls directly from lead screens"},
    {"code": "INBOUND_CALLING", "display_name": "Inbound Calling", "category": "Calls", "icon": "PhoneIncoming", "description": "Receive calls within the CRM console"},
    {"code": "OUTBOUND_CALLING", "display_name": "Outbound Calling", "category": "Calls", "icon": "PhoneOutgoing", "description": "Place outgoing telephony calls"},
    {"code": "CALL_RECORDING", "display_name": "Call Recording", "category": "Calls", "icon": "Mic", "description": "Record conversation audio for quality control"},
    {"code": "CALL_DISPOSITION", "display_name": "Call Disposition Management", "category": "Calls", "icon": "CheckSquare", "description": "Set status and remarks for call logs"},

    # Dashboards & Analytics
    {"code": "BASIC_DASHBOARD", "display_name": "Basic Dashboard", "category": "Analytics", "icon": "LayoutDashboard", "description": "Access simple lead metrics and graphs"},
    {"code": "MANAGER_DASHBOARD", "display_name": "Manager Dashboard", "category": "Analytics", "icon": "PieChart", "description": "Track team pipelines, targets, and performances"},
    {"code": "TEAM_LEADER_DASHBOARD", "display_name": "Team Leader Dashboard", "category": "Analytics", "icon": "BarChart", "description": "Supervise assigned agents and leads progress"},
    {"code": "TEAM_MONITORING", "display_name": "Team Performance Monitoring", "category": "Analytics", "icon": "Activity", "description": "Monitor real-time status and activity timelines"},
    {"code": "TARGET_MANAGEMENT", "display_name": "Target Management", "category": "Analytics", "icon": "Target", "description": "Configure performance quotas and targets for agents"},
    {"code": "KPI_DASHBOARD", "display_name": "KPI Dashboard", "category": "Analytics", "icon": "TrendingUp", "description": "Review key business performance indicators"},
    {"code": "CONVERSION_ANALYTICS", "display_name": "Conversion Analytics", "category": "Analytics", "icon": "TrendingUp", "description": "Deep-dive conversion funnel visualization"},
]

async def seed():
    async with async_session_maker() as session:
        logger.info("Initializing database session for SaaS seed...")
        
        # 1. Clean up ALL existing records to start with a fresh blank state
        logger.info("Purging old databases...")
        await session.execute(delete(Note))
        await session.execute(delete(Activity))
        await session.execute(delete(Lead))
        await session.execute(delete(Contact))
        await session.execute(delete(Company))
        await session.execute(delete(PipelineStage))
        await session.execute(delete(PerformanceTarget))
        await session.execute(delete(UserSession))
        await session.execute(delete(UserInvitation))
        await session.execute(delete(AuditLog))
        await session.execute(delete(Payment))
        await session.execute(delete(Invoice))
        await session.execute(delete(TenantSubscription))
        await session.execute(delete(User))
        await session.execute(delete(Organization))
        await session.execute(delete(PlanFeature))
        await session.execute(delete(Plan))
        await session.execute(delete(Feature))
        await session.execute(delete(SystemSetting))
        await session.execute(delete(InvoiceConfig))
        await session.execute(delete(CommercialSettings))
        await session.commit()
        logger.info("Database purge completed.")

        # 2. Create the SuperAdmin Organization
        org_repo = OrganizationRepository(session)
        org = await org_repo.create({"name": "Johnson Softwares", "slug": "johnsonsoftwares"})
        logger.info(f"Created SuperAdmin organization: {org.name} (id: {org.id})")

        # 3. Create the SuperAdmin User
        pwd_hash = get_password_hash("Password123")
        admin_user = User(
            organization_id=org.id,
            email="admin@johnsonsoftwares.com",
            hashed_password=pwd_hash,
            first_name="Johnson",
            last_name="Softwares",
            role="SuperAdmin",
            is_active=True,
            is_verified=True
        )
        session.add(admin_user)
        await session.flush()
        logger.info(f"Created SuperAdmin User: admin@johnsonsoftwares.com (name: Johnson)")

        # 4. Seed Dynamic Feature Registry
        logger.info("Seeding master feature registry...")
        for feature_data in FEATURES:
            feature = Feature(
                code=feature_data["code"],
                display_name=feature_data["display_name"],
                category=feature_data["category"],
                icon=feature_data["icon"],
                description=feature_data["description"],
                active=True
            )
            session.add(feature)

        # 5. Seed default invoice configuration
        logger.info("Seeding default invoice configuration...")
        invoice_config = InvoiceConfig(
            id="default",
            company_name="Johnson Softwares",
            tagline="Enterprise CRM & Telephony Solutions",
            website="www.johnsonsoftwares.com",
            support_email="support@johnsonsoftwares.com",
            phone_number="+1-123-456-7890",
            address="101, Antigravity Heights, Google DeepMind St, BKC, Mumbai - 400051",
            gst_number="27AAAAA1111A1Z1",
            pan="ABCDE1234F",
            business_registration_number="U12345MH2026PTC123456",
            invoice_prefix="INV-2026",
            starting_invoice_number=1001,
            currency="INR",
            currency_symbol="₹",
            bank_name="HDFC Bank",
            account_holder="Johnson Softwares Private Limited",
            account_number="50100012345678",
            ifsc="HDFC0000123",
            branch="BKC Branch",
            upi_id="johnsonsoftwares@upi",
            payment_terms="<p>Payment Due within 15 Days</p><p>Late Fee Applicable</p><p>Subscription Suspended after 30 Days</p>",
            footer_text="<p>Thank you for choosing Johnson Softwares.</p><p>This invoice is system generated.</p>",
            invoice_subject="Invoice {invoice_number} from Johnson Softwares",
            invoice_body="Dear {customer_name},\n\nPlease find attached invoice {invoice_number} for your subscription.\n\nBest regards,\nJohnson Softwares",
            reminder_subject="Payment Reminder: Invoice {invoice_number}",
            reminder_body="Dear {customer_name},\n\nThis is a friendly reminder that invoice {invoice_number} is due on {due_date}.\n\nBest regards,\nJohnson Softwares",
            payment_success_subject="Payment Received: Invoice {invoice_number}",
            payment_success_body="Dear {customer_name},\n\nWe have received payment for invoice {invoice_number}. Thank you!\n\nBest regards,\nJohnson Softwares",
            payment_failed_subject="Payment Failed: Invoice {invoice_number}",
            payment_failed_body="Dear {customer_name},\n\nWe attempted to charge your account for invoice {invoice_number}, but the payment failed.\n\nPlease update your payment details.\n\nBest regards,\nJohnson Softwares",
            renewal_reminder_subject="Your Subscription Renewal is Coming Up",
            renewal_reminder_body="Dear {customer_name},\n\nYour subscription will renew on {renewal_date}.\n\nBest regards,\nJohnson Softwares"
        )
        session.add(invoice_config)
        
        # 6. Seed default commercial settings
        logger.info("Seeding default commercial settings...")
        commercial_settings = CommercialSettings(
            id="default",
            default_currency="INR",
            currency_symbol="₹",
            default_timezone="Asia/Kolkata",
            default_gst=18.0,
            gst_inclusive=False,
            tax_label="GST",
            default_trial_days=14,
            allow_trial=True,
            trial_reminder_days=3,
            default_min_contract=3,
            auto_renewal=True,
            notice_period_days=15,
            default_setup_charge=0.0,
            allow_setup_discount=True,
            free_setup_on_annual=True,
            default_extra_user_price=0.0,
            minimum_users=10,
            maximum_users=None,
            default_discount_percentage=0.0,
            maximum_discount_percentage=25.0,
            late_payment_charge=0.0,
            late_payment_type="flat",
            grace_period_days=7,
            auto_suspend_days=30,
            auto_reactivate=True,
            reminder_schedule="{}",
            invoice_reminder_days="7,3,1",
            subscription_reminder_days="15,7,3,0",
            payment_reminder_days="0,3,7,15",
            default_plan_id=None,
            default_recording_retention_days=90,
            default_storage_gb=50,
            invoice_reminder_template="Dear {customer_name},\n\nThis is a reminder for your upcoming invoice {invoice_number}.\n\nRegards,\nManagement",
            renewal_reminder_template="Dear {customer_name},\n\nYour subscription is renewing soon.\n\nRegards,\nManagement",
            trial_expiry_template="Dear {customer_name},\n\nYour trial is expiring in {days_left} days. Upgrade now!\n\nRegards,\nManagement",
            payment_success_template="Dear {customer_name},\n\nPayment for invoice {invoice_number} was successful.\n\nRegards,\nManagement",
            payment_failed_template="Dear {customer_name},\n\nPayment for invoice {invoice_number} has failed. Please verify.\n\nRegards,\nManagement",
            welcome_template="Dear {customer_name},\n\nWelcome to our platform!\n\nRegards,\nManagement"
        )
        session.add(commercial_settings)
        
        # 7. Commit all changes
        await session.commit()
        logger.info("SaaS Database Seeding successfully completed!")

if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)

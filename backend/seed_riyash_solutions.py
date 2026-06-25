import asyncio
import logging
import random
import sys
import uuid
from datetime import datetime, date, time, timedelta, timezone
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
from app.models.target import PerformanceTarget, TargetType, MetricType
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.tenant_subscription import TenantSubscription
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.payment import Payment
from app.models.system_setting import SystemSetting
from app.models.invoice_config import InvoiceConfig
from app.models.commercial_settings import CommercialSettings
from app.models.assignment_config import AssignmentConfig
from app.models.lead_import import LeadImport

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_riyash")

# Complete feature registry matching requirements
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

    # Additional Features
    {"code": "CONTACT_MANAGEMENT", "display_name": "Contact Management", "category": "Leads", "icon": "Users", "description": "Manage contacts directory"},
    {"code": "BASIC_REPORTS", "display_name": "Basic Reports", "category": "Reports", "icon": "FileText", "description": "Basic reports generation"},
    {"code": "CSV_IMPORT", "display_name": "CSV Import", "category": "Leads", "icon": "Upload", "description": "Import leads from CSV files"},
    {"code": "EXCEL_IMPORT", "display_name": "Excel Import", "category": "Leads", "icon": "Upload", "description": "Import leads from Excel files"},
    {"code": "PRIORITY_SUPPORT", "display_name": "Priority Support", "category": "Support", "icon": "LifeBuoy", "description": "Fast priority support"},
    {"code": "AI_CALL_SUMMARY", "display_name": "AI Call Summary", "category": "AI", "icon": "Cpu", "description": "AI summaries of call recordings"},
    {"code": "AI_FOLLOW_UP", "display_name": "AI Follow-up Recommendations", "category": "AI", "icon": "Brain", "description": "AI follow-up action recommendations"},
    {"code": "API_ACCESS", "display_name": "API Access", "category": "API", "icon": "Code", "description": "External integration API access"},
    {"code": "CUSTOM_REPORTS", "display_name": "Custom Reports", "category": "Reports", "icon": "FileBarChart", "description": "Build custom reporting dashboards"},
    {"code": "DEDICATED_ACCOUNT_MANAGER", "display_name": "Dedicated Account Manager", "category": "Support", "icon": "User", "description": "Dedicated representative support"},
    {"code": "PRIORITY_SLA", "display_name": "Priority SLA", "category": "Support", "icon": "ShieldAlert", "description": "Uptime and response SLAs"},
    
    # Navigation dependencies
    {"code": "SALES_PIPELINE", "display_name": "Sales Pipeline", "category": "Leads", "icon": "Workflow", "description": "Manage custom sales pipelines"},
    {"code": "ROLE_BASED_ACCESS", "display_name": "Role-Based Access Control", "category": "Administration", "icon": "Shield", "description": "Granular user permission tiers"},
]

PLAN_SPEC = {
    "Starter": {
        "price_monthly": 3999.0,
        "price_quarterly": 11997.0,
        "price_annual": 47988.0,
        "max_users": 10,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "extra_user_price": 3999.0,
        "allow_additional_seats": True,
        "storage_limit_gb": 10,
        "recording_retention_days": 30,
        "priority_support": False,
        "api_access": False,
        "features": [
            "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "CLICK_TO_CALL", "CALL_RECORDING",
            "BASIC_DASHBOARD", "BASIC_REPORTS", "CSV_IMPORT", "EXCEL_IMPORT",
            "OUTBOUND_CALLING", "CALL_DISPOSITION"
        ]
    },
    "Growth": {
        "price_monthly": 4999.0,
        "price_quarterly": 14997.0,
        "price_annual": 59988.0,
        "max_users": 15,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "extra_user_price": 4999.0,
        "allow_additional_seats": True,
        "storage_limit_gb": 200,
        "recording_retention_days": 180,
        "priority_support": True,
        "api_access": False,
        "features": [
            "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "CLICK_TO_CALL", "CALL_RECORDING",
            "BASIC_DASHBOARD", "BASIC_REPORTS", "CSV_IMPORT", "EXCEL_IMPORT",
            "OUTBOUND_CALLING", "CALL_DISPOSITION", "INBOUND_CALLING",
            "BULK_ASSIGNMENT", "BULK_TRANSFER", "GOOGLE_SHEETS_IMPORT",
            "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD", "TARGET_MANAGEMENT", "KPI_DASHBOARD",
            "SALES_PIPELINE", "ROLE_BASED_ACCESS", "PRIORITY_SUPPORT", "TEAM_MONITORING"
        ]
    },
    "Enterprise AI": {
        "price_monthly": 7500.0,
        "price_quarterly": 22500.0,
        "price_annual": 90000.0,
        "max_users": 20,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "extra_user_price": 7500.0,
        "allow_additional_seats": True,
        "storage_limit_gb": 1000,
        "recording_retention_days": 365,
        "priority_support": True,
        "api_access": True,
        "features": [
            "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "CLICK_TO_CALL", "CALL_RECORDING",
            "BASIC_DASHBOARD", "BASIC_REPORTS", "CSV_IMPORT", "EXCEL_IMPORT",
            "OUTBOUND_CALLING", "CALL_DISPOSITION", "INBOUND_CALLING",
            "BULK_ASSIGNMENT", "BULK_TRANSFER", "GOOGLE_SHEETS_IMPORT",
            "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD", "TARGET_MANAGEMENT", "KPI_DASHBOARD",
            "SALES_PIPELINE", "ROLE_BASED_ACCESS", "PRIORITY_SUPPORT", "TEAM_MONITORING",
            "AI_CALL_SUMMARY", "AI_FOLLOW_UP", "API_ACCESS", "CUSTOM_REPORTS",
            "DEDICATED_ACCOUNT_MANAGER", "PRIORITY_SLA", "CONVERSION_ANALYTICS", "SMART_DISTRIBUTION"
        ]
    }
}

INDIAN_COMPANIES = [
    "Zenith Technologies Pvt Ltd", "TechVantage Solutions", "Apex Enterprises", "Royal Paints India Ltd",
    "Intech Systems", "Shanti Logistics Pvt Ltd", "Mahadev Steel & Alloys", "Bharat Agri Solutions",
    "Mumbai Digital Media", "Royal Orchid Hotels Ltd", "Deccan Healthcare", "Sonalika Tractors Bkc",
    "Paramount Diagnostics", "Tata Steel Bkc Division", "Blue Star HVAC Group", "Godrej Consumer Goods",
    "Reliance Retail Bkc", "Wipro Infotech Bkc Center", "Kotak Securities BKC", "Aditya Birla Capital",
    "HDFC Mutual Fund", "ICICI Prudential", "L&T Financial Services", "Mahindra Logistics", "Tata Power",
    "Kirloskar Engines Ltd", "Crompton Greaves Pvt Ltd", "Hindalco Industries", "Ambuja Cements BKC",
    "UltraTech Cement", "Jindal Steel & Power Ltd", "JSW Energy BKC", "Adani Ports BKC", "Sun Pharma",
    "Dr Reddy's Laboratories", "Cipla Healthcare Ltd", "Lupin Limited", "Aurobindo Pharma", "Cadila Healthcare",
    "Glenmark Pharmaceuticals", "Divi's Laboratories Ltd", "Biocon India Ltd", "Torrent Pharmaceuticals",
    "Alkem Laboratories", "Abbott India Ltd", "Pfizer India BKC", "GlaxoSmithKline India", "Sanofi India",
    "Novartis India", "Bayer CropScience BKC"
]

FIRST_NAMES = [
    "Amit", "Anand", "Anil", "Arvind", "Ashish", "Ashok", "Balaji", "Chandran", "Deepak", "Dinesh",
    "Ganesh", "Hari", "Jagdish", "Jitendra", "Kalyan", "Kishore", "Madhav", "Manoj", "Murali", "Nitin",
    "Prakash", "Prashant", "Raghav", "Ramesh", "Sanjay", "Satish", "Suresh", "Venkat", "Vijay", "Vikram",
    "Anjali", "Asha", "Deepa", "Geeta", "Indu", "Jyothi", "Kavitha", "Lakshmi", "Madhavi", "Meena",
    "Nalini", "Neeta", "Padma", "Pooja", "Radha", "Rajani", "Rekha", "Sandhya", "Sarita", "Shanthi",
    "Sneha", "Sudha", "Swati", "Uma", "Vani", "Vidya"
]

LAST_NAMES = [
    "Kumar", "Sharma", "Patel", "Gupta", "Mehta", "Rao", "Nair", "Joshi", "Reddy", "Sen",
    "Iyer", "Deshmukh", "Kulkarni", "Shinde", "Patil", "Jha", "Mishra", "Singh", "Prasad", "Choudhury",
    "Das", "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Roy", "Bose", "Dutta", "Mitra", "Pal",
    "Saha", "Kar", "De", "Ray", "Dasgupta", "Majumdar", "Chakraborty", "Ganguly", "Bhattacharya", "Som",
    "Nandy"
]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad", "Chennai"]
TITLES = ["Founder", "Director", "CTO", "CEO", "Head of Sales", "Purchase Manager", "VP Engineering"]
REMARKS_POOL = [
    "Spoke with customer. They are checking pricing details.",
    "Interested in the Growth plan. Scheduled a product demo.",
    "Requires custom API integration information.",
    "Will discuss with team and get back next week.",
    "Busy at the moment. Asked to call back later.",
    "No response. Sent automated follow-up WhatsApp.",
    "Wrong number or not reachable.",
    "Happy with current vendor but open to comparison sheet.",
    "Needs dedicated support details.",
    "Requested PDF proposal via email.",
    "Discussed storage and call recording features.",
    "Number out of service.",
    "Asked not to call again.",
    "High potential lead, ready for conversion."
]

async def get_or_create_features(session: AsyncSession) -> dict:
    """Ensure all required features exist in the system and return map of code -> UUID."""
    feature_map = {}
    for f in FEATURES:
        # Check if feature exists
        stmt = select(Feature).where(Feature.code == f["code"])
        res = await session.execute(stmt)
        feature = res.scalar_one_or_none()
        if not feature:
            feature = Feature(
                code=f["code"],
                display_name=f["display_name"],
                category=f["category"],
                icon=f["icon"],
                description=f["description"],
                active=True
            )
            session.add(feature)
            await session.flush()
        feature_map[f["code"]] = feature.id
    return feature_map

async def seed_plans(session: AsyncSession, feature_map: dict) -> dict:
    """Seed Starter, Growth, and Enterprise plans with plan features."""
    plan_map = {}
    for plan_name, spec in PLAN_SPEC.items():
        stmt = select(Plan).where(Plan.name == plan_name)
        res = await session.execute(stmt)
        plan = res.scalar_one_or_none()
        
        # Clean up existing features mapping if plan exists
        if plan:
            plan.plan_features.clear()
            await session.flush()
        else:
            plan = Plan(name=plan_name)
        
        # Map fields
        plan.display_name = plan_name
        plan.description = f"Enterprise-grade {plan_name} package"
        plan.monthly_price = spec["price_monthly"]
        plan.quarterly_price = spec["price_quarterly"]
        plan.annual_price = spec["price_annual"]
        plan.price_inr = spec["price_monthly"]
        plan.currency = "INR"
        plan.max_users = spec["max_users"]
        plan.minimum_users = spec["minimum_users"]
        plan.maximum_users = spec["maximum_users"]
        plan.minimum_contract_months = spec["minimum_contract_months"]
        plan.extra_user_price = spec["extra_user_price"]
        plan.allow_additional_seats = spec["allow_additional_seats"]
        plan.storage_limit_gb = spec["storage_limit_gb"]
        plan.recording_retention_days = spec["recording_retention_days"]
        plan.priority_support = spec["priority_support"]
        plan.api_access = spec["api_access"]
        plan.is_active = True
        plan.plan_active = True
        plan.is_trial = False
        plan.features = {code: True for code in spec["features"]}
        
        session.add(plan)
        await session.flush()
        plan_map[plan_name] = plan.id
        
        # Add Plan Features
        for code in spec["features"]:
            feat_uuid = feature_map.get(code)
            if feat_uuid:
                pf = PlanFeature(
                    plan_id=plan.id,
                    feature_id=feat_uuid,
                    enabled=True
                )
                session.add(pf)
        await session.flush()
        
    return plan_map

async def clean_existing_tenant(session: AsyncSession, org_slug: str):
    """Purge all existing records associated with the slug to allow fresh seed re-runs."""
    stmt = select(Organization).where(Organization.slug == org_slug)
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()
    
    if org:
        logger.info(f"Existing Riyash tenant found (ID: {org.id}). Purging records...")
        await session.execute(delete(Note).where(Note.organization_id == org.id))
        await session.execute(delete(Activity).where(Activity.organization_id == org.id))
        await session.execute(delete(Lead).where(Lead.organization_id == org.id))
        await session.execute(delete(Contact).where(Contact.organization_id == org.id))
        await session.execute(delete(Company).where(Company.organization_id == org.id))
        await session.execute(delete(PipelineStage).where(PipelineStage.organization_id == org.id))
        await session.execute(delete(PerformanceTarget).where(PerformanceTarget.organization_id == org.id))
        await session.execute(delete(UserSession).where(UserSession.user_id.in_(
            select(User.id).where(User.organization_id == org.id)
        )))
        await session.execute(delete(UserInvitation).where(UserInvitation.organization_id == org.id))
        await session.execute(delete(AuditLog).where(AuditLog.organization_id == org.id))
        await session.execute(delete(Payment).where(Payment.invoice_id.in_(
            select(Invoice.id).where(Invoice.organization_id == org.id)
        )))
        await session.execute(delete(Invoice).where(Invoice.organization_id == org.id))
        await session.execute(delete(TenantSubscription).where(TenantSubscription.organization_id == org.id))
        await session.execute(delete(User).where(User.organization_id == org.id))
        await session.execute(delete(AssignmentConfig).where(AssignmentConfig.organization_id == org.id))
        await session.execute(delete(LeadImport).where(LeadImport.organization_id == org.id))
        await session.execute(delete(Organization).where(Organization.id == org.id))
        await session.commit()
        logger.info("Purged old Riyash Solutions tenant data.")

async def seed():
    async with async_session_maker() as session:
        logger.info("Starting demo seeding execution...")
        
        # 1. Feature Registry
        feature_map = await get_or_create_features(session)
        logger.info(f"Verified {len(feature_map)} features in database.")
        
        # 2. Setup Plans
        plan_map = await seed_plans(session, feature_map)
        logger.info(f"Configured 3 plans: Starter, Growth, Enterprise.")
        
        # 3. Clean target tenant
        slug = "riyash"
        await clean_existing_tenant(session, slug)
        
        # 4. Create Organization
        org = Organization(
            name="Riyash Solutions Pvt Ltd",
            slug=slug,
            is_active=True,
            subscription_plan="Growth",
            subscription_status="active",
            max_users=15,
            extra_storage_gb=0, # Built-in 200 GB limit on Growth
            website="www.riyashsolutions.com",
            support_email="riyashsolutions@gmail.com",
            support_phone="+91 98765 43210",
            timezone="Asia/Kolkata",
            language="English",
            currency="INR",
            billing_name="Riyash Solutions Private Limited",
            gst_number="27AAACR1234A1Z1",
            pan="AAACR1234A",
            billing_address="501, BKC Corporate Park, BKC",
            billing_city="Mumbai",
            billing_state="Maharashtra",
            billing_country="India",
            billing_pin_code="400051",
            billing_email="billing@riyashsolutions.com",
            billing_phone="+91 98765 43210",
            theme="dark",
            auto_renewal=True
        )
        session.add(org)
        await session.flush()
        logger.info(f"Created Riyash Solutions organization (id: {org.id})")
        
        # 5. Create Tenant Subscription
        now_utc = datetime.now(timezone.utc)
        sub = TenantSubscription(
            organization_id=org.id,
            plan_id=plan_map["Growth"],
            status="active",
            start_date=now_utc - timedelta(days=15),
            end_date=now_utc + timedelta(days=75), # 3 Months subscription length
            auto_renew=True,
            billing_cycle="quarterly",
            users_purchased=15,
            users_active=6,
            storage_used=120.45,
            call_recording_usage=500
        )
        session.add(sub)
        await session.flush()
        
        # Set subscription reference back on organization for convenience
        org.subscription_expires_at = sub.end_date.replace(tzinfo=None)
        session.add(org)
        await session.flush()
        
        # 6. Seed Invoices & Payments History
        invoice1 = Invoice(
            organization_id=org.id,
            invoice_number="INV-RIYASH-001",
            amount=10500.0, # 3500 * 3 months
            status="Paid",
            payment_status="paid",
            due_date=(now_utc - timedelta(days=10)).replace(tzinfo=None),
            issue_date=now_utc - timedelta(days=15),
            plan_name="Growth",
            amount_inr=10500.0,
            currency="INR",
            subscription_id=sub.id,
            setup_charges=0.0,
            extra_users_amount=0.0,
            discount_amount=0.0,
            gst_amount=1890.0, # 18% of 10500
            total_amount=12390.0
        )
        session.add(invoice1)
        await session.flush()
        
        pay1 = Payment(
            invoice_id=invoice1.id,
            payment_reference="PAY-RIYASH-001",
            gateway="UPI",
            status="Paid",
            transaction_id="TXN-RIYASH-111222",
            paid_date=now_utc - timedelta(days=15),
            remarks="Initial subscription fee paid."
        )
        session.add(pay1)
        
        # Unpaid reminder invoice
        invoice2 = Invoice(
            organization_id=org.id,
            invoice_number="INV-RIYASH-002",
            amount=3500.0,
            status="Pending",
            payment_status="unpaid",
            due_date=(now_utc + timedelta(days=15)).replace(tzinfo=None),
            issue_date=now_utc,
            plan_name="Growth Extra Seats",
            amount_inr=3500.0,
            currency="INR",
            subscription_id=sub.id,
            setup_charges=0.0,
            extra_users_amount=3500.0,
            discount_amount=0.0,
            gst_amount=630.0,
            total_amount=4130.0
        )
        session.add(invoice2)
        await session.flush()
        
        # 7. Seed Demo Users Hierarchy
        pwd_hash = get_password_hash("Password123")
        
        # 1. Sunil (OrgAdmin)
        sunil = User(
            organization_id=org.id,
            email="riyashsolutions@gmail.com",
            hashed_password=pwd_hash,
            first_name="Sunil",
            last_name="Reddy",
            role="OrgAdmin",
            is_active=True,
            is_verified=True,
            reporting_to_id=None
        )
        session.add(sunil)
        await session.flush()
        
        # 2. Rajesh (Manager), reports to Sunil
        rajesh = User(
            organization_id=org.id,
            email="rajesh@riyashsolutions.com",
            hashed_password=pwd_hash,
            first_name="Rajesh",
            last_name="Kumar",
            role="Manager",
            is_active=True,
            is_verified=True,
            reporting_to_id=sunil.id
        )
        session.add(rajesh)
        await session.flush()
        
        # 3. Priya (Employee - Team Leader), reports to Rajesh
        priya = User(
            organization_id=org.id,
            email="priya@riyashsolutions.com",
            hashed_password=pwd_hash,
            first_name="Priya",
            last_name="Sharma",
            role="Employee", # Reports to Manager => TL
            is_active=True,
            is_verified=True,
            reporting_to_id=rajesh.id
        )
        session.add(priya)
        await session.flush()
        
        # Telecallers reporting to Priya (TL)
        arun = User(
            organization_id=org.id,
            email="arun@riyashsolutions.com",
            hashed_password=pwd_hash,
            first_name="Arun",
            last_name="Singh",
            role="Employee", # Reports to TL => Telecaller
            is_active=True,
            is_verified=True,
            reporting_to_id=priya.id
        )
        session.add(arun)
        
        divya = User(
            organization_id=org.id,
            email="divya@riyashsolutions.com",
            hashed_password=pwd_hash,
            first_name="Divya",
            last_name="Patel",
            role="Employee",
            is_active=True,
            is_verified=True,
            reporting_to_id=priya.id
        )
        session.add(divya)
        
        karthik = User(
            organization_id=org.id,
            email="karthik@riyashsolutions.com",
            hashed_password=pwd_hash,
            first_name="Karthik",
            last_name="Joshi",
            role="Employee",
            is_active=True,
            is_verified=True,
            reporting_to_id=priya.id
        )
        session.add(karthik)
        await session.flush()
        logger.info("Seeded employee reporting hierarchy: Sunil -> Rajesh -> Priya -> (Arun, Divya, Karthik)")

        # 8. Seed Pipeline Stages
        stages = [
            {"name": "New", "order": 1, "default": True},
            {"name": "Contacted", "order": 2, "default": False},
            {"name": "Interested", "order": 3, "default": False},
            {"name": "Scheduled Demo", "order": 4, "default": False},
            {"name": "Converted", "order": 5, "default": False},
            {"name": "Lost", "order": 6, "default": False},
            {"name": "Dropped", "order": 7, "default": False}
        ]
        
        stage_map = {}
        for s in stages:
            stage = PipelineStage(
                organization_id=org.id,
                name=s["name"],
                order_position=s["order"],
                is_system_default=s["default"]
            )
            session.add(stage)
            await session.flush()
            stage_map[s["name"]] = stage.id
        logger.info("Seeded pipeline stages.")
        
        # 9. Seed Leads (150 Total: 20 Converted, 10 Lost, 20 Scheduled Demo, and 100 others)
        telecallers = [arun, divya, karthik]
        agents_pool = [arun, divya, karthik, priya]
        
        leads = []
        
        lead_configurations = [
            {"status": "Converted", "stage": "Converted", "count": 20},
            {"status": "Lost", "stage": "Lost", "count": 10},
            {"status": "Scheduled Demo", "stage": "Scheduled Demo", "count": 20},
            {"status": "New", "stage": "New", "count": 40},
            {"status": "Contacted", "stage": "Contacted", "count": 40},
            {"status": "Interested", "stage": "Interested", "count": 20}
        ]
        
        lead_counter = 0
        now_date = date.today()
        
        for config in lead_configurations:
            status_val = config["status"]
            stage_name = config["stage"]
            count = config["count"]
            
            for i in range(count):
                lead_counter += 1
                
                # Pick Indian names
                fn = random.choice(FIRST_NAMES)
                ln = random.choice(LAST_NAMES)
                email = f"{fn.lower()}.{ln.lower()}{lead_counter}@gmail.com"
                phone = f"+91 9{random.randint(10000000, 99999999)}"
                company = random.choice(INDIAN_COMPANIES)
                title = random.choice(TITLES)
                city = random.choice(CITIES)
                value = float(random.randint(15, 95) * 1000)
                
                # Distribute creation dates over past 15 days
                # Ensure exactly 15 leads are created "Today"
                if lead_counter <= 15:
                    created_at_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 6))
                else:
                    days_ago = random.randint(1, 14)
                    created_at_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(1, 10))
                
                assigned_agent = random.choice(agents_pool)
                
                lead = Lead(
                    organization_id=org.id,
                    first_name=fn,
                    last_name=ln,
                    email=email,
                    phone=phone,
                    company_name=company,
                    title=title,
                    city=city,
                    status=status_val,
                    value=value,
                    assigned_user_id=assigned_agent.id,
                    created_by=sunil.id,
                    stage_id=stage_map[stage_name],
                    call_attempts_count=0,
                    created_at=created_at_time
                )
                session.add(lead)
                await session.flush()
                leads.append(lead)
                
        logger.info(f"Seeded {len(leads)} leads successfully.")
        
        # 10. Generate 500 Call Records (using Outbound Calls and Lead Dispositions Audit Logs)
        # We distribute these 500 calls across telecallers Arun, Divya, Karthik (~150 each) and Priya (~50)
        # Exactly 60 calls must happen "Today" to show high telemetry on dashboard
        call_durations = [0, 0, 45, 90, 120, 180, 240, 310]
        dispositions = [
            ("Answered / Resolved", "Picked"),
            ("RNR", "RNR"),
            ("Busy", "Busy"),
            ("Switch Off", "Switch Off"),
            ("Interested", "Picked"),
            ("Callback Requested", "Picked")
        ]
        
        total_calls_to_seed = 500
        calls_seeded = 0
        
        for k in range(total_calls_to_seed):
            # Select a random lead
            lead = random.choice(leads)
            
            # Determine calling agent
            agent = None
            for a in agents_pool:
                if a.id == lead.assigned_user_id:
                    agent = a
                    break
            if not agent:
                agent = random.choice(telecallers)
            
            # Timestamp distribution
            if calls_seeded < 60:
                # Placed today
                call_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 7), minutes=random.randint(0, 50))
            else:
                days_ago = random.randint(1, 14)
                call_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(1, 9), minutes=random.randint(0, 50))
            
            # Pick a disposition based on lead status
            if lead.status == "Converted":
                disp_val, p_status = ("Interested", "Picked")
            elif lead.status == "Lost":
                disp_val, p_status = random.choice([("Not Interested", "Picked"), ("Busy", "Busy"), ("RNR", "RNR")])
            else:
                disp_val, p_status = random.choice(dispositions)
                
            dur = random.choice(call_durations) if p_status == "Picked" else 0
            
            call_sid = f"call_sid_{uuid.uuid4().hex[:16]}"
            recording_url = f"https://spaces.riyashsolutions.com/recordings/{call_sid}.mp3" if dur > 0 else None
            
            # 1. Create call activity
            call_activity = Activity(
                organization_id=org.id,
                activity_type="Call",
                subject=f"Outbound Call: {disp_val}",
                description=f"Outbound call made to {lead.first_name} {lead.last_name} ({lead.company_name}). Disposition status: {disp_val}.",
                status="Completed",
                assigned_user_id=agent.id,
                lead_id=lead.id,
                created_by=agent.id,
                call_sid=call_sid,
                recording_url=recording_url,
                call_duration=dur,
                call_direction="OUTBOUND",
                created_at=call_time
            )
            session.add(call_activity)
            
            # 2. Generate matching disposition audit log
            audit_log = AuditLog(
                organization_id=org.id,
                actor_user_id=agent.id,
                action="LEAD_DISPOSITION_SUBMITTED",
                resource_type="Lead",
                resource_id=str(lead.id),
                action_metadata={
                    "status": disp_val,
                    "remarks": random.choice(REMARKS_POOL),
                    "previous_stage_id": str(lead.stage_id),
                    "new_stage_id": str(lead.stage_id),
                    "call_attempts_count": lead.call_attempts_count + 1,
                    "available_at": None
                },
                created_at=call_time
            )
            session.add(audit_log)
            
            # Update lead metrics
            lead.call_attempts_count += 1
            session.add(lead)
            
            calls_seeded += 1
            if calls_seeded % 50 == 0:
                await session.flush()
                
        logger.info(f"Seeded {calls_seeded} call logs and audit records.")
        
        # 11. Seed Follow-ups (50 total: 30 planned pending, 20 completed tasks)
        followup_seeded = 0
        
        # 30 Planned Pending Follow-ups (due in next 5 days)
        for i in range(30):
            lead = random.choice(leads)
            agent = random.choice(telecallers)
            due = datetime.now(timezone.utc) + timedelta(days=random.randint(1, 5), hours=random.randint(1, 8))
            
            task = Activity(
                organization_id=org.id,
                activity_type="Task",
                subject="Follow-up Call regarding proposal",
                description="Client requested a callback to discuss price proposal details.",
                due_date=due,
                status="Planned",
                assigned_user_id=agent.id,
                lead_id=lead.id,
                created_by=priya.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 3))
            )
            session.add(task)
            followup_seeded += 1
            
        # 20 Completed Follow-ups
        for i in range(20):
            lead = random.choice(leads)
            agent = random.choice(telecallers)
            due = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5), hours=random.randint(1, 8))
            
            task = Activity(
                organization_id=org.id,
                activity_type="Task",
                subject="Follow-up Call completed",
                description="Discussed core requirements and moved to Interested list.",
                due_date=due,
                status="Completed",
                assigned_user_id=agent.id,
                lead_id=lead.id,
                created_by=priya.id,
                created_at=due - timedelta(days=1)
            )
            session.add(task)
            followup_seeded += 1
            
        logger.info(f"Seeded {followup_seeded} follow-up activities.")
        
        # 12. Create 20 Scheduled Demos (planned/completed activities)
        demo_leads = [l for l in leads if l.status == "Scheduled Demo"]
        demo_count = 0
        for dl in demo_leads:
            agent = random.choice(telecallers)
            
            # 10 completed demos (past) and 10 planned demos (future)
            if demo_count < 10:
                status_v = "Completed"
                due = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5), hours=random.randint(1, 4))
            else:
                status_v = "Planned"
                due = datetime.now(timezone.utc) + timedelta(days=random.randint(1, 5), hours=random.randint(1, 4))
                
            demo_activity = Activity(
                organization_id=org.id,
                activity_type="Meeting",
                subject=f"Product Demo: {dl.company_name}",
                description=f"Detailed SaaS platform walkthrough for {dl.first_name} {dl.last_name} ({dl.title}).",
                due_date=due,
                status=status_v,
                assigned_user_id=agent.id,
                lead_id=dl.id,
                created_by=priya.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=2)
            )
            session.add(demo_activity)
            demo_count += 1
            
        logger.info(f"Seeded {demo_count} Scheduled Demo activities.")
        
        # 13. Seed Performance Targets for June 2026
        target1 = PerformanceTarget(
            organization_id=org.id,
            target_type=TargetType.MONTHLY,
            metric_type=MetricType.CALLS_MADE,
            target_value=1000,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30)
        )
        session.add(target1)
        
        target2 = PerformanceTarget(
            organization_id=org.id,
            target_type=TargetType.MONTHLY,
            metric_type=MetricType.LEADS_CONVERTED,
            target_value=50,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30)
        )
        session.add(target2)
        logger.info("Seeded performance targets for June 2026.")
        
        # Commit all transactions
        await session.commit()
        logger.info("All demo data for Riyash Solutions seeded successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        logger.error(f"Demo seeding failed: {e}")
        sys.exit(1)

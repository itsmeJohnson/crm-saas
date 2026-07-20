"""
Seeds one demo tenant per common telecalling/sales business vertical:
Real Estate, Loan Recovery (Collections), General Telecalling Sales,
Insurance & Banking, EdTech, Healthcare/Diagnostics, E-commerce/D2C,
Digital Marketing Agency, Recruitment Agency, Automobile Showroom, and
Logistics.

Each tenant gets its own org, a small reporting hierarchy (OrgAdmin -> Manager
-> Team Lead -> 2 Telecallers), a pipeline tailored to that business, and a
batch of realistic leads. Re-running is safe: a vertical whose org doesn't
exist yet gets fully created; one that already exists is topped up with
more leads (using its existing pipeline/agents) until it reaches
LEADS_PER_VERTICAL, so bumping the target count and re-running is enough
to grow existing demo tenants too.

Usage: python seed_demo_verticals.py
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.plan import Plan
from app.models.tenant_subscription import TenantSubscription

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_demo_verticals")

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
    "Das", "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Roy", "Bose", "Dutta", "Mitra", "Pal"
]
CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad", "Chennai", "Ahmedabad", "Kolkata"]

PASSWORD = "Demo@12345"


def random_person():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def random_phone():
    return f"+91 9{random.randint(10000000, 99999999)}"


# ── Per-vertical lead vocabulary ─────────────────────────────────────────────

VERTICALS = [
    {
        "slug": "primehomes-realty",
        "org_name": "PrimeHomes Realty",
        "admin_email": "admin@primehomesrealty.com",
        "stages": ["New", "Contacted", "Site Visit Scheduled", "Site Visited", "Negotiation", "Booked", "Lost"],
        "stage_weights": [25, 20, 15, 15, 10, 8, 7],
        "titles": [
            "2BHK Apartment Inquiry", "3BHK Apartment Inquiry", "Villa Purchase Inquiry",
            "Commercial Office Space Inquiry", "Plot Purchase Inquiry", "Investment Property Inquiry",
            "Resale Flat Inquiry", "Under-Construction Project Inquiry"
        ],
        "companies": [
            "Lodha Group", "Godrej Properties", "Prestige Group", "Sobha Limited", "Brigade Group",
            "DLF Homes", "Oberoi Realty", "Shapoorji Pallonji RE", "Self-funded Buyer", "NRI Investor"
        ],
        "sources": ["99acres", "Housing.com", "MagicBricks", "Site Walk-in", "Referral", "Facebook Ads"],
        "value_range": (1_500_000, 9_000_000),
    },
    {
        "slug": "swiftrecover-collections",
        "org_name": "SwiftRecover Collections",
        "admin_email": "admin@swiftrecover.com",
        "stages": ["New", "Contacted", "PTP Given", "Partial Payment", "Settled", "Escalated", "Written Off"],
        "stage_weights": [20, 25, 18, 12, 12, 8, 5],
        "titles": [
            "Personal Loan EMI Default", "Credit Card Overdue Payment", "Auto Loan EMI Default",
            "Consumer Durable Loan Default", "Business Loan Overdue", "Two-Wheeler Loan Default"
        ],
        "companies": [
            "Bajaj Finserv", "HDFC Bank", "ICICI Bank", "Tata Capital", "Fullerton India",
            "IDFC First Bank", "Axis Finance", "Muthoot Finance", "L&T Finance", "Cholamandalam Finance"
        ],
        "sources": ["Bucket 1 (0-30 days)", "Bucket 2 (31-60 days)", "Bucket 3 (61-90 days)", "NPA Referral"],
        "value_range": (8_000, 350_000),
    },
    {
        "slug": "novasell-outbound",
        "org_name": "NovaSell Outbound Sales",
        "admin_email": "admin@novasell.com",
        "stages": ["New", "Contacted", "Interested", "Demo Scheduled", "Converted", "Lost"],
        "stage_weights": [25, 25, 18, 14, 10, 8],
        "titles": [
            "CRM Software Inquiry", "Office Stationery Bulk Order", "Annual AMC Renewal Inquiry",
            "Broadband Plan Upgrade Inquiry", "Office Furniture Inquiry", "Corporate Gifting Inquiry"
        ],
        "companies": [
            "Zenith Technologies", "Apex Enterprises", "Mumbai Digital Media", "Bharat Agri Solutions",
            "Shanti Logistics", "Intech Systems", "Royal Paints India", "TechVantage Solutions"
        ],
        "sources": ["Cold Call List", "Website Form", "LinkedIn Outreach", "Trade Show", "Referral"],
        "value_range": (10_000, 250_000),
    },
    {
        "slug": "securefirst-insurance",
        "org_name": "SecureFirst Insurance & Banking",
        "admin_email": "admin@securefirst.com",
        "stages": ["New", "Contacted", "Quote Shared", "Policy Issued", "Card Approved", "Lost"],
        "stage_weights": [25, 25, 20, 12, 10, 8],
        "titles": [
            "Term Insurance Inquiry", "Health Insurance Family Floater Inquiry", "Car Insurance Renewal",
            "Credit Card Cross-sell", "Personal Loan Pre-approved Offer", "ULIP Investment Inquiry"
        ],
        "companies": [
            "HDFC Life", "ICICI Lombard", "LIC of India", "Max Bupa", "SBI Life", "Star Health",
            "Axis Bank Cards", "Kotak Mahindra Bank", "Bajaj Allianz", "Tata AIA"
        ],
        "sources": ["Inbound IVR", "Bank Database", "Renewal Reminder List", "Branch Walk-in", "Aggregator Lead"],
        "value_range": (5_000, 500_000),
    },
    {
        "slug": "brightpath-edtech",
        "org_name": "BrightPath EdTech",
        "admin_email": "admin@brightpathedu.com",
        "stages": ["New", "Contacted", "Counseling Scheduled", "Demo Attended", "Enrolled", "Lost"],
        "stage_weights": [28, 24, 18, 14, 10, 6],
        "titles": [
            "Data Science Course Inquiry", "Full Stack Development Course Inquiry", "UPSC Coaching Inquiry",
            "Spoken English Course Inquiry", "Class 10 Tuition Inquiry", "MBA Entrance Coaching Inquiry"
        ],
        "companies": [
            "Self (Working Professional)", "Self (College Student)", "Parent Enquiry", "Self (Job Seeker)"
        ],
        "sources": ["Instagram Ads", "YouTube Ad Lead Form", "Website Free Demo", "Referral", "Education Fair"],
        "value_range": (8_000, 180_000),
    },
    {
        "slug": "vitalcare-diagnostics",
        "org_name": "VitalCare Diagnostics",
        "admin_email": "admin@vitalcarediagnostics.com",
        "stages": ["New", "Contacted", "Appointment Booked", "Test Done", "Report Delivered", "Lost"],
        "stage_weights": [25, 25, 20, 15, 8, 7],
        "titles": [
            "Full Body Checkup Inquiry", "Diabetes Profile Test Inquiry", "MRI Scan Inquiry",
            "Corporate Health Camp Inquiry", "Senior Citizen Health Package Inquiry", "COVID Antibody Test Inquiry"
        ],
        "companies": [
            "Self / Individual", "Infosys (Corporate Camp)", "TCS (Corporate Camp)", "Wipro (Corporate Camp)",
            "Self / Senior Citizen", "Referring Physician"
        ],
        "sources": ["Hospital Website", "Health Camp Walk-in", "Referral Doctor", "Phone Helpline", "Google Ads"],
        "value_range": (1_500, 25_000),
    },
    {
        "slug": "urbancart-d2c",
        "org_name": "UrbanCart D2C",
        "admin_email": "admin@urbancart.com",
        "stages": ["New", "Contacted", "Order Confirmed", "Payment Pending", "Order Placed", "Lost"],
        "stage_weights": [30, 22, 16, 12, 12, 8],
        "titles": [
            "Cart Abandonment Follow-up", "COD Order Confirmation", "Bulk Order Inquiry",
            "Product Availability Inquiry", "Return / Exchange Request Inquiry", "Festive Sale Inquiry"
        ],
        "companies": ["Self / Individual Buyer", "Reseller", "Gifting Order"],
        "sources": ["Website Cart Abandonment", "Instagram Shop", "WhatsApp Catalog", "Meta Ads", "Referral"],
        "value_range": (500, 15_000),
    },
    {
        "slug": "pixelreach-marketing",
        "org_name": "PixelReach Marketing Agency",
        "admin_email": "admin@pixelreach.com",
        "stages": ["New", "Contacted", "Proposal Sent", "Negotiation", "Onboarded", "Lost"],
        "stage_weights": [28, 24, 18, 14, 10, 6],
        "titles": [
            "SEO Services Inquiry", "Social Media Management Inquiry", "Performance Marketing Inquiry",
            "Website Redesign Inquiry", "Branding & Creative Inquiry", "Influencer Marketing Inquiry"
        ],
        "companies": [
            "Zenith Technologies", "Royal Orchid Hotels", "Deccan Healthcare", "Bharat Agri Solutions",
            "Mumbai Digital Media", "D2C Startup Founder", "Local Restaurant Chain", "Real Estate Developer"
        ],
        "sources": ["LinkedIn Outreach", "Referral", "Google Ads", "Website Contact Form", "Cold Email"],
        "value_range": (15_000, 400_000),
    },
    {
        "slug": "talentbridge-recruitment",
        "org_name": "TalentBridge Recruitment",
        "admin_email": "admin@talentbridge.com",
        "stages": ["New", "Contacted", "Resume Shared", "Interview Scheduled", "Offer Released", "Placed", "Lost"],
        "stage_weights": [25, 22, 16, 14, 10, 7, 6],
        "titles": [
            "Software Engineer Role Inquiry", "Sales Manager Hiring Request", "Bulk Hiring - BPO Associates",
            "Senior Leadership Search", "Contract Staffing Request", "Campus Hiring Drive Inquiry"
        ],
        "companies": [
            "Wipro Infotech", "Kotak Securities", "Aditya Birla Capital", "Tata Steel", "Reliance Retail",
            "Blue Star HVAC Group", "Godrej Consumer Goods", "Self / Job Seeker"
        ],
        "sources": ["Naukri.com", "LinkedIn", "Referral", "Company Website", "Job Fair"],
        "value_range": (20_000, 600_000),
    },
    {
        "slug": "velocity-motors",
        "org_name": "Velocity Motors Showroom",
        "admin_email": "admin@velocitymotors.com",
        "stages": ["New", "Contacted", "Test Drive Scheduled", "Test Drive Done", "Booking Confirmed", "Delivered", "Lost"],
        "stage_weights": [25, 22, 16, 14, 12, 6, 5],
        "titles": [
            "Hatchback Purchase Inquiry", "SUV Purchase Inquiry", "Sedan Purchase Inquiry",
            "Electric Vehicle Inquiry", "Exchange Offer Inquiry", "Service & Maintenance Inquiry"
        ],
        "companies": [
            "Self / Individual Buyer", "Corporate Fleet - Infosys", "Corporate Fleet - TCS",
            "Self / First-time Buyer", "Self / Upgrade Buyer"
        ],
        "sources": ["Showroom Walk-in", "CarDekho", "CarWale", "Referral", "Festive Offer Campaign"],
        "value_range": (450_000, 2_500_000),
    },
    {
        "slug": "swifttrack-logistics",
        "org_name": "SwiftTrack Logistics",
        "admin_email": "admin@swifttracklogistics.com",
        "stages": ["New", "Contacted", "Quote Shared", "Contract Signed", "Onboarded", "Lost"],
        "stage_weights": [28, 24, 18, 14, 10, 6],
        "titles": [
            "Full Truck Load Inquiry", "Part Load Shipment Inquiry", "Warehousing Inquiry",
            "Last Mile Delivery Partnership", "Cold Chain Logistics Inquiry", "Express Courier Bulk Inquiry"
        ],
        "companies": [
            "Reliance Retail", "Godrej Consumer Goods", "Mahindra Logistics Client", "Local D2C Brand",
            "Bharat Agri Solutions", "Tata Steel BKC Division", "Mumbai Digital Media"
        ],
        "sources": ["Website Quote Form", "Referral", "Trade Show", "Cold Call List", "IndiaMART"],
        "value_range": (25_000, 800_000),
    },
]

LEADS_PER_VERTICAL = 150


async def top_up_leads(session, spec: dict, org: Organization, needed: int):
    """Add `needed` more leads to an already-seeded org, reusing its existing
    pipeline stages and agents instead of recreating org/users."""
    stage_rows = await session.execute(
        select(PipelineStage.id, PipelineStage.name).where(PipelineStage.organization_id == org.id)
    )
    stage_map = {name: sid for sid, name in stage_rows.all()}
    if not stage_map:
        logger.warning(f"'{spec['org_name']}' has no pipeline stages - skipping top-up.")
        return 0

    agent_rows = await session.execute(
        select(User.id).where(User.organization_id == org.id, User.role == "Employee", User.is_active == True)
    )
    agent_ids = [row[0] for row in agent_rows.all()]
    admin_row = await session.execute(
        select(User.id).where(User.organization_id == org.id, User.role == "OrgAdmin")
    )
    admin_id = admin_row.scalar_one_or_none()
    if not agent_ids or not admin_id:
        logger.warning(f"'{spec['org_name']}' is missing agents/admin - skipping top-up.")
        return 0

    lo, hi = spec["value_range"]
    stage_names = [s for s in spec["stages"] if s in stage_map]
    weights = [w for s, w in zip(spec["stages"], spec["stage_weights"]) if s in stage_map]

    for i in range(needed):
        stage_name = random.choices(stage_names, weights=weights, k=1)[0]
        fn, ln = random_person()
        value = float(random.randint(int(lo), int(hi)))
        days_ago = random.randint(0, 20)
        created_at_time = datetime.now(timezone.utc) - timedelta(
            days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )
        lead = Lead(
            organization_id=org.id,
            first_name=fn,
            last_name=ln,
            email=f"{fn.lower()}.{ln.lower()}{random.randint(1000, 999999)}@gmail.com",
            phone=random_phone(),
            company_name=random.choice(spec["companies"]),
            title=random.choice(spec["titles"]),
            city=random.choice(CITIES),
            source=random.choice(spec["sources"]),
            status=stage_name,
            value=value,
            assigned_user_id=random.choice(agent_ids),
            created_by=admin_id,
            stage_id=stage_map[stage_name],
            call_attempts_count=random.randint(0, 6),
            created_at=created_at_time,
        )
        session.add(lead)
    return needed


async def seed_vertical(session, spec: dict):
    existing = await session.execute(
        select(Organization).where(Organization.slug == spec["slug"])
    )
    org = existing.scalar_one_or_none()
    if org:
        count_res = await session.execute(
            select(Lead.id).where(Lead.organization_id == org.id)
        )
        current_count = len(count_res.all())
        needed = LEADS_PER_VERTICAL - current_count
        if needed <= 0:
            logger.info(f"Skipping '{spec['org_name']}' - already has {current_count} leads.")
            return
        added = await top_up_leads(session, spec, org, needed)
        logger.info(f"Topped up '{spec['org_name']}': +{added} leads (had {current_count}, now {current_count + added}).")
        return

    org = Organization(
        name=spec["org_name"],
        slug=spec["slug"],
        is_active=True,
        subscription_plan="Growth",
        subscription_status="active",
        subscription_expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).replace(tzinfo=None),
        max_users=20,
    )
    session.add(org)
    await session.flush()

    growth_plan_res = await session.execute(
        select(Plan).where(Plan.name == "Growth", Plan.is_deleted == False)
    )
    growth_plan = growth_plan_res.scalar_one_or_none()
    if growth_plan:
        now_utc = datetime.now(timezone.utc)
        subscription = TenantSubscription(
            organization_id=org.id,
            plan_id=growth_plan.id,
            status="active",
            start_date=now_utc,
            end_date=now_utc + timedelta(days=365),
            auto_renew=True,
            billing_cycle="monthly",
            users_purchased=org.max_users,
            users_active=1,
        )
        session.add(subscription)
        await session.flush()
    else:
        logger.warning(f"Growth plan not found - '{spec['org_name']}' created without a TenantSubscription row.")

    pwd_hash = get_password_hash(PASSWORD)

    admin = User(
        organization_id=org.id, email=spec["admin_email"], hashed_password=pwd_hash,
        first_name="Org", last_name="Admin", role="OrgAdmin", is_active=True, is_verified=True
    )
    session.add(admin)
    await session.flush()

    mgr_fn, mgr_ln = random_person()
    manager = User(
        organization_id=org.id, email=f"manager@{spec['slug']}.com", hashed_password=pwd_hash,
        first_name=mgr_fn, last_name=mgr_ln, role="Manager", is_active=True, is_verified=True
    )
    session.add(manager)
    await session.flush()

    tl_fn, tl_ln = random_person()
    team_lead = User(
        organization_id=org.id, email=f"teamlead@{spec['slug']}.com", hashed_password=pwd_hash,
        first_name=tl_fn, last_name=tl_ln, role="Employee", is_active=True, is_verified=True,
        reporting_to_id=manager.id
    )
    session.add(team_lead)
    await session.flush()

    telecallers = []
    for i in range(2):
        fn, ln = random_person()
        tc = User(
            organization_id=org.id, email=f"telecaller{i + 1}@{spec['slug']}.com", hashed_password=pwd_hash,
            first_name=fn, last_name=ln, role="Employee", is_active=True, is_verified=True,
            reporting_to_id=team_lead.id
        )
        session.add(tc)
        telecallers.append(tc)
    await session.flush()

    stage_map = {}
    for order, stage_name in enumerate(spec["stages"], start=1):
        stage = PipelineStage(
            organization_id=org.id, name=stage_name, order_position=order, is_system_default=(order == 1)
        )
        session.add(stage)
        await session.flush()
        stage_map[stage_name] = stage.id

    agents_pool = telecallers + [team_lead]
    lo, hi = spec["value_range"]
    leads_created = 0
    for i in range(LEADS_PER_VERTICAL):
        stage_name = random.choices(spec["stages"], weights=spec["stage_weights"], k=1)[0]
        fn, ln = random_person()
        title = random.choice(spec["titles"])
        company = random.choice(spec["companies"])
        source = random.choice(spec["sources"])
        city = random.choice(CITIES)
        value = float(random.randint(int(lo), int(hi)))
        days_ago = random.randint(0, 20)
        created_at_time = datetime.now(timezone.utc) - timedelta(
            days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )
        agent = random.choice(agents_pool)

        lead = Lead(
            organization_id=org.id,
            first_name=fn,
            last_name=ln,
            email=f"{fn.lower()}.{ln.lower()}{i}@gmail.com",
            phone=random_phone(),
            company_name=company,
            title=title,
            city=city,
            source=source,
            status=stage_name,
            value=value,
            assigned_user_id=agent.id,
            created_by=admin.id,
            stage_id=stage_map[stage_name],
            call_attempts_count=random.randint(0, 6),
            created_at=created_at_time,
        )
        session.add(lead)
        leads_created += 1

    logger.info(f"Seeded '{spec['org_name']}' ({spec['slug']}): {leads_created} leads, "
                f"admin={spec['admin_email']} / password={PASSWORD}")


async def main():
    async with async_session_maker() as session:
        for spec in VERTICALS:
            await seed_vertical(session, spec)
        await session.commit()
    logger.info("Done. All demo verticals seeded (or already present).")


if __name__ == "__main__":
    asyncio.run(main())

"""
1. Soft-delete all orgs EXCEPT Johnson Softwares (admin@johnsonsoftwares.com)
2. Create one demo tenant per new plan: CoreCRM / Professional / Business
3. Each tenant gets: OrgAdmin + Manager + Team Leader + 2 Employees
4. All seeded with TenantSubscription linked to the correct plan

Credentials for all demo users: Demo@12345
"""

import asyncio, sys, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/crm",
)

SAFE_EMAIL = "admin@johnsonsoftwares.com"
PASSWORD   = "Demo@12345"

DEMO_TENANTS = [
    {
        "plan_name":   "CoreCRM",
        "org_name":    "CoreCRM Demo Co.",
        "slug":        "corecrm-demo",
        "admin_email": "admin@corecrm-demo.com",
        "users": [
            {"first": "Arjun",  "last": "Mehta",   "role": "Manager",  "tl": False},
            {"first": "Priya",  "last": "Sharma",  "role": "Employee", "tl": True,  "reports_to": "Manager"},
            {"first": "Rohan",  "last": "Verma",   "role": "Employee", "tl": False, "reports_to": "TL"},
            {"first": "Sneha",  "last": "Patel",   "role": "Employee", "tl": False, "reports_to": "TL"},
        ],
    },
    {
        "plan_name":   "Professional",
        "org_name":    "Professional Demo Co.",
        "slug":        "professional-demo",
        "admin_email": "admin@professional-demo.com",
        "users": [
            {"first": "Karan",   "last": "Singh",   "role": "Manager",  "tl": False},
            {"first": "Divya",   "last": "Nair",    "role": "Employee", "tl": True,  "reports_to": "Manager"},
            {"first": "Amit",    "last": "Kumar",   "role": "Employee", "tl": False, "reports_to": "TL"},
            {"first": "Meena",   "last": "Joshi",   "role": "Employee", "tl": False, "reports_to": "TL"},
        ],
    },
    {
        "plan_name":   "Business",
        "org_name":    "Business Demo Co.",
        "slug":        "business-demo",
        "admin_email": "admin@business-demo.com",
        "users": [
            {"first": "Vikram",  "last": "Reddy",   "role": "Manager",  "tl": False},
            {"first": "Neha",    "last": "Gupta",   "role": "Employee", "tl": True,  "reports_to": "Manager"},
            {"first": "Suresh",  "last": "Pillai",  "role": "Employee", "tl": False, "reports_to": "TL"},
            {"first": "Anjali",  "last": "Rao",     "role": "Employee", "tl": False, "reports_to": "TL"},
        ],
    },
]


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        from app.models.organization import Organization
        from app.models.user import User
        from app.models.plan import Plan
        from app.models.tenant_subscription import TenantSubscription
        from app.models.pipeline import PipelineStage
        from app.core.security import get_password_hash

        now = datetime.now(timezone.utc)

        # ── 1. Find safe org ───────────────────────────────────────────────
        safe_user = (await db.execute(
            select(User).where(User.email == SAFE_EMAIL, User.is_deleted == False)
        )).scalar_one_or_none()
        if not safe_user:
            print(f"ERROR: {SAFE_EMAIL} not found. Aborting.")
            return
        safe_org_id = safe_user.organization_id
        print(f"Keeping org: {safe_org_id} ({SAFE_EMAIL})\n")

        # ── 2. Soft-delete all other orgs and their users ──────────────────
        all_orgs = (await db.execute(
            select(Organization).where(Organization.is_deleted == False)
        )).scalars().all()

        deleted_orgs = 0
        for org in all_orgs:
            if org.id == safe_org_id:
                continue
            # soft-delete users
            await db.execute(
                update(User)
                .where(User.organization_id == org.id)
                .values(is_deleted=True, is_active=False)
            )
            org.is_deleted = True
            org.is_active = False
            deleted_orgs += 1
            print(f"  Deleted org: {org.name}")

        await db.flush()
        print(f"\nDeleted {deleted_orgs} tenant(s).\n")

        # ── 3. Create demo tenants ─────────────────────────────────────────
        for t in DEMO_TENANTS:
            plan = (await db.execute(
                select(Plan).where(Plan.name == t["plan_name"], Plan.is_deleted == False)
            )).scalar_one_or_none()
            if not plan:
                print(f"ERROR: plan '{t['plan_name']}' not found. Skipping.")
                continue

            # Create org
            org = Organization(
                name=t["org_name"],
                slug=t["slug"],
                is_active=True,
                subscription_plan=plan.display_name,
                subscription_status="active",
                subscription_expires_at=(now + timedelta(days=365)).replace(tzinfo=None),
                max_users=plan.max_users,
            )
            db.add(org)
            await db.flush()

            # Create TenantSubscription
            sub = TenantSubscription(
                organization_id=org.id,
                plan_id=plan.id,
                status="active",
                start_date=now.replace(tzinfo=None),
                end_date=(now + timedelta(days=365)).replace(tzinfo=None),
                auto_renew=True,
                billing_cycle="monthly",
                users_purchased=plan.minimum_users,
                users_active=1,
            )
            db.add(sub)
            await db.flush()

            # Create OrgAdmin
            admin = User(
                organization_id=org.id,
                email=t["admin_email"],
                hashed_password=get_password_hash(PASSWORD),
                first_name="Demo",
                last_name="Admin",
                role="OrgAdmin",
                is_active=True,
            )
            db.add(admin)
            await db.flush()

            # Track role→user id for reporting structure
            # TL = Employee whose reporting_to_id points to a Manager
            manager_id = None
            tl_id = None

            for u in t["users"]:
                email = f"{u['first'].lower()}.{u['last'].lower()}@{t['slug']}.demo"
                reporting = None
                if u.get("reports_to") == "Manager":
                    reporting = manager_id   # TL reports to Manager
                elif u.get("reports_to") == "TL":
                    reporting = tl_id        # Employees report to TL

                new_user = User(
                    organization_id=org.id,
                    email=email,
                    hashed_password=get_password_hash(PASSWORD),
                    first_name=u["first"],
                    last_name=u["last"],
                    role=u["role"],
                    reporting_to_id=reporting,
                    is_active=True,
                )
                db.add(new_user)
                await db.flush()

                if u["role"] == "Manager":
                    manager_id = new_user.id
                if u.get("tl"):
                    tl_id = new_user.id

            # Default pipeline stages (PipelineStage links directly to org)
            for i, stage in enumerate(["New Lead", "Contacted", "Interested", "Negotiation", "Won", "Lost"], 1):
                db.add(PipelineStage(organization_id=org.id, name=stage, order_position=i))

            total_users = 1 + len(t["users"])  # admin + team
            print(f"  Created '{t['org_name']}' on {plan.display_name} plan")
            print(f"    Admin: {t['admin_email']} / {PASSWORD}")
            print(f"    Team: {total_users} users total\n")

        await db.commit()
        print("All done.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

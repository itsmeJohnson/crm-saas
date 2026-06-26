"""
seed_plans.py — Non-destructive seed for Plans + Demo Tenant
-------------------------------------------------------------
Safe to run multiple times — skips existing records.

Usage (inside Docker):
    docker compose exec backend python seed_plans.py

Usage (local Python):
    cd backend && python seed_plans.py
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.organization import Organization
from app.models.user import User
from app.models.tenant_subscription import TenantSubscription
from app.models.system_setting import SystemSetting

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_plans")


# ─────────────────────────────────────────────────────────────────────────────
# Plan definitions — field names match actual Plan model columns
# ─────────────────────────────────────────────────────────────────────────────
PLANS = [
    {
        # ₹3,999/user/month × 10 users = ₹39,990 + 18% GST = ₹47,188.20/month
        "name": "starter",
        "display_name": "Starter Plan",
        "description": "Perfect for small sales teams getting started with CRM and telecalling.",
        "monthly_price": 3999.0,       # per user/month
        "quarterly_price": 11997.0,    # 3999 × 3 months per user
        "annual_price": 47988.0,       # 3999 × 12 months per user
        "currency": "INR",
        "minimum_users": 10,
        "maximum_users": 50,
        "allow_additional_seats": True,
        "extra_user_price": 3999.0,    # same rate for add-on seats
        "storage_limit_gb": 50,
        "recording_retention_days": 30,
        "setup_charges": 0.0,
        "minimum_contract_months": 3,
        "trial_days": 14,
        "gst_percentage": 18.0,        # +18% GST on total
        "discount_percentage": 0.0,
        "display_order": 1,
        "plan_badge": None,
        "plan_color": "#6366f1",
        "plan_active": True,
        "price_per_seat": 3999.0,
    },
    {
        # ₹4,999/user/month × 10 users = ₹49,990 + 18% GST = ₹58,988.20/month
        "name": "professional",
        "display_name": "Professional Plan",
        "description": "For growing teams that need advanced analytics, pipelines, and full telephony.",
        "monthly_price": 4999.0,       # per user/month
        "quarterly_price": 14997.0,    # 4999 × 3 months per user
        "annual_price": 59988.0,       # 4999 × 12 months per user
        "currency": "INR",
        "minimum_users": 10,
        "maximum_users": 200,
        "allow_additional_seats": True,
        "extra_user_price": 4999.0,
        "storage_limit_gb": 100,
        "recording_retention_days": 90,
        "setup_charges": 0.0,
        "minimum_contract_months": 3,
        "trial_days": 0,
        "gst_percentage": 18.0,
        "discount_percentage": 0.0,
        "display_order": 2,
        "plan_badge": "Popular",
        "plan_color": "#8b5cf6",
        "plan_active": True,
        "popular_plan": True,
        "price_per_seat": 4999.0,
    },
    {
        # ₹7,999/user/month × 10 users = ₹79,990 + 18% GST = ₹94,388.20/month
        "name": "enterprise",
        "display_name": "Enterprise Plan",
        "description": "Unlimited scale with dedicated support, custom integrations, and SLA.",
        "monthly_price": 7999.0,       # per user/month
        "quarterly_price": 23997.0,    # 7999 × 3 months per user
        "annual_price": 95988.0,       # 7999 × 12 months per user
        "currency": "INR",
        "minimum_users": 25,
        "maximum_users": 5000,
        "allow_additional_seats": True,
        "extra_user_price": 7999.0,
        "storage_limit_gb": 500,
        "recording_retention_days": 365,
        "setup_charges": 0.0,
        "minimum_contract_months": 6,
        "trial_days": 0,
        "gst_percentage": 18.0,
        "discount_percentage": 5.0,   # 5% loyalty discount
        "display_order": 3,
        "plan_badge": "Best Value",
        "plan_color": "#f59e0b",
        "plan_active": True,
        "recommended_plan": True,
        "dedicated_manager": True,
        "price_per_seat": 7999.0,
    },
]

PLAN_FEATURES = {
    "starter": [
        "LEAD_MANAGEMENT", "BULK_ASSIGNMENT", "CLICK_TO_CALL",
        "OUTBOUND_CALLING", "CALL_DISPOSITION", "BASIC_DASHBOARD",
        "ROLE_BASED_ACCESS",
    ],
    "professional": [
        "LEAD_MANAGEMENT", "BULK_ASSIGNMENT", "BULK_TRANSFER", "SMART_DISTRIBUTION",
        "GOOGLE_SHEETS_IMPORT", "CLICK_TO_CALL", "INBOUND_CALLING", "OUTBOUND_CALLING",
        "CALL_RECORDING", "CALL_DISPOSITION", "BASIC_DASHBOARD", "MANAGER_DASHBOARD",
        "TEAM_LEADER_DASHBOARD", "TEAM_MONITORING", "TARGET_MANAGEMENT",
        "CONVERSION_ANALYTICS", "SALES_PIPELINE", "ROLE_BASED_ACCESS",
        "CONTACT_MANAGEMENT", "COMPANY_MANAGEMENT",
    ],
    "enterprise": [
        "LEAD_MANAGEMENT", "BULK_ASSIGNMENT", "BULK_TRANSFER", "SMART_DISTRIBUTION",
        "GOOGLE_SHEETS_IMPORT", "CLICK_TO_CALL", "INBOUND_CALLING", "OUTBOUND_CALLING",
        "CALL_RECORDING", "CALL_DISPOSITION", "BASIC_DASHBOARD", "MANAGER_DASHBOARD",
        "TEAM_LEADER_DASHBOARD", "TEAM_MONITORING", "TARGET_MANAGEMENT", "KPI_DASHBOARD",
        "CONVERSION_ANALYTICS", "SALES_PIPELINE", "ROLE_BASED_ACCESS",
        "CONTACT_MANAGEMENT", "COMPANY_MANAGEMENT", "ADVANCED_ANALYTICS",
        "CUSTOM_PIPELINE", "CUSTOM_REPORTS",
    ],
}

DEMO_TENANT = {
    "name": "Riyash Solutions",
    "slug": "riyash-solutions",
    "admin_email": "admin@riyashsolutions.com",
    "admin_password": "Demo@1234",
    "first_name": "Riyash",
    "last_name": "Kumar",
    "plan_name": "professional",
    "licensed_seats": 10,
    "subscription_months": 12,
}


async def seed():
    async with async_session_maker() as session:

        # ── 1. Seed Plans ────────────────────────────────────────────────────
        logger.info("Seeding plans...")
        created_plans: dict[str, Plan] = {}

        for pd in PLANS:
            plan_name = pd["name"]
            existing = (await session.execute(
                select(Plan).where(Plan.name == plan_name)
            )).scalar_one_or_none()

            if existing:
                logger.info(f"  Plan '{plan_name}' already exists — skipping")
                created_plans[plan_name] = existing
                continue

            plan = Plan(**pd)
            session.add(plan)
            await session.flush()
            created_plans[plan_name] = plan
            logger.info(f"  ✅ Created plan: {pd['display_name']}")

        await session.commit()

        # ── 2. Seed Plan Features ────────────────────────────────────────────
        logger.info("Seeding plan-feature mappings...")

        all_features = (await session.execute(select(Feature))).scalars().all()
        feature_map = {f.code: f for f in all_features}

        if not feature_map:
            logger.warning("  No features found in DB — skipping feature mapping")
        else:
            for plan_name, codes in PLAN_FEATURES.items():
                plan = created_plans.get(plan_name)
                if not plan:
                    continue
                for code in codes:
                    feature = feature_map.get(code)
                    if not feature:
                        logger.warning(f"  Feature '{code}' not in DB — skipping")
                        continue
                    exists = (await session.execute(
                        select(PlanFeature).where(
                            PlanFeature.plan_id == plan.id,
                            PlanFeature.feature_id == feature.id,
                        )
                    )).scalar_one_or_none()
                    if not exists:
                        session.add(PlanFeature(
                            plan_id=plan.id,
                            feature_id=feature.id,
                            enabled=True,   # correct column name (not is_enabled)
                        ))
            await session.commit()
            logger.info("  ✅ Plan-feature mappings done")

        # ── 3. Create Demo Tenant ────────────────────────────────────────────
        logger.info("Seeding demo tenant...")
        dt = DEMO_TENANT

        existing_org = (await session.execute(
            select(Organization).where(Organization.slug == dt["slug"])
        )).scalar_one_or_none()

        if existing_org:
            logger.info(f"  Demo tenant '{dt['slug']}' already exists — skipping")
        else:
            plan = created_plans.get(dt["plan_name"])
            now_aware = datetime.now(timezone.utc)
            now_naive = datetime.utcnow()  # naive — for TIMESTAMP WITHOUT TIME ZONE columns
            expires_naive = now_naive + timedelta(days=dt["subscription_months"] * 30)

            org = Organization(
                name=dt["name"],
                slug=dt["slug"],
                is_active=True,
                subscription_plan=dt["plan_name"],
                subscription_status="active",
                subscription_expires_at=expires_naive,  # naive — column has no tz
                max_users=dt["licensed_seats"],
            )
            session.add(org)
            await session.flush()

            session.add(User(
                organization_id=org.id,
                email=dt["admin_email"],
                hashed_password=get_password_hash(dt["admin_password"]),
                first_name=dt["first_name"],
                last_name=dt["last_name"],
                role="OrgAdmin",
                is_active=True,
                is_verified=True,
            ))

            if plan:
                expires_aware = now_aware + timedelta(days=dt["subscription_months"] * 30)
                session.add(TenantSubscription(
                    organization_id=org.id,
                    plan_id=plan.id,
                    status="active",
                    start_date=now_aware,
                    end_date=expires_aware,
                    users_purchased=dt["licensed_seats"],
                    users_active=1,
                    billing_cycle="monthly",
                ))

            await session.commit()
            logger.info(f"  ✅ Created tenant: {dt['name']}")
            logger.info(f"     Login: {dt['admin_email']} / {dt['admin_password']}")

        # ── 4. Set default plan in system settings ───────────────────────────
        starter = created_plans.get("starter")
        if starter:
            existing_setting = (await session.execute(
                select(SystemSetting).where(SystemSetting.key == "default_plan_id")
            )).scalar_one_or_none()
            if not existing_setting:
                session.add(SystemSetting(
                    key="default_plan_id",
                    value=str(starter.id),
                ))
                await session.commit()
                logger.info("  ✅ Set Starter as default plan")

        logger.info("\n🎉 Seed complete!")
        logger.info("=" * 60)
        logger.info("Plans: Starter / Professional / Enterprise")
        logger.info(f"Demo tenant: {DEMO_TENANT['name']}")
        logger.info(f"  Admin login: {DEMO_TENANT['admin_email']} / {DEMO_TENANT['admin_password']}")
        logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        logger.error(f"Seed failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

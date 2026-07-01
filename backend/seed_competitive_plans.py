"""
Seed 3 clean competitive plans:
  1. Core CRM       — no calling, ₹1,199/seat/month
  2. Professional   — calling built-in (pay-per-minute), ₹1,999/seat/month
  3. Business       — calling built-in (flat-rate unlimited), ₹4,999/seat/month

Calling cost context:
  - Knowlarity per-min cost: ₹0.40/min + 18% GST = ₹0.47/min
  - We charge tenants: ₹0.65/min (29% margin)
  - Knowlarity flat: ₹3,000/user/month + 18% GST = ₹3,540
  - Business plan: ₹4,999 → ₹1,459 margin on calling per user
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/crm",
)

# Feature sets per plan
CORE_FEATURES = {
    "BASIC_DASHBOARD", "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT",
    "SALES_PIPELINE", "BULK_IMPORT", "ROLE_BASED_ACCESS",
    "DASHBOARD_REPORTS", "FOLLOW_UP_TASKS", "LEAD_DISTRIBUTION",
    "LEAD_TRANSFERS", "BULK_ASSIGNMENT", "BULK_TRANSFER",
}

PROFESSIONAL_FEATURES = CORE_FEATURES | {
    "CLICK_TO_CALL", "OUTBOUND_CALLING", "INBOUND_CALLING",
    "CALL_RECORDING", "CALL_DISPOSITION",
    "CONVERSION_ANALYTICS", "KPI_DASHBOARD", "MANAGER_DASHBOARD",
    "TEAM_LEADER_DASHBOARD", "TARGET_MANAGEMENT", "TEAM_MONITORING",
    "SMART_DISTRIBUTION", "ADVANCED_PIPELINE",
}

BUSINESS_FEATURES = PROFESSIONAL_FEATURES | {
    "ADVANCED_ANALYTICS", "CUSTOM_PIPELINE", "CUSTOM_REPORTS",
    "AI_CALL_SUMMARY", "AI_FOLLOW_UP", "API_ACCESS",
    "GOOGLE_SHEETS_IMPORT", "PRIORITY_SUPPORT",
}

PLANS = [
    {
        "name": "CoreCRM",
        "display_name": "Core CRM",
        "description": (
            "Pure CRM for teams that use their own dialer or telephony. "
            "Covers the full lead lifecycle — import, assign, track, report. "
            "Integrated calling available as an add-on at ₹0.65/min + GST."
        ),
        "monthly_price": 1199.0,
        "quarterly_price": 1079.0,
        "annual_price": 959.0,
        "extra_user_price": 1199.0,
        "currency": "INR",
        "max_users": 10000,
        "max_admins": 100, "max_managers": 100,
        "max_team_leads": 100, "max_employees": 100,
        "storage_limit_gb": 10,
        "recording_retention_days": 0,
        "priority_support": False,
        "api_access": False,
        "display_order": 20,
        "setup_charges": 0.0,
        "minimum_users": 5,
        "maximum_users": 1000,
        "minimum_contract_months": 1,
        "trial_days": 14,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#6366f1",
        "plan_badge": "No Calling",
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": False,
        "allow_trial": True,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        "_features": CORE_FEATURES,
    },
    {
        "name": "Professional",
        "display_name": "Professional",
        "description": (
            "Full CRM with built-in click-to-call, inbound & outbound dialer, "
            "call recording, and team KPI tracking. "
            "Calling billed on usage at ₹0.65/min + GST — pay only for what you use."
        ),
        "monthly_price": 1999.0,
        "quarterly_price": 1799.0,
        "annual_price": 1599.0,
        "extra_user_price": 1999.0,
        "currency": "INR",
        "max_users": 10000,
        "max_admins": 100, "max_managers": 100,
        "max_team_leads": 100, "max_employees": 100,
        "storage_limit_gb": 10,
        "recording_retention_days": 90,
        "priority_support": True,
        "api_access": False,
        "display_order": 21,
        "setup_charges": 0.0,
        "minimum_users": 5,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "trial_days": 14,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#8b5cf6",
        "plan_badge": "Most Popular",
        "popular_plan": True,
        "recommended_plan": True,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": True,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        "_features": PROFESSIONAL_FEATURES,
    },
    {
        "name": "Business",
        "display_name": "Business",
        "description": (
            "All-inclusive CRM for high-volume telecalling teams. "
            "Unlimited calling with no per-minute charges, AI call summaries, "
            "custom reports, API access, and priority support. "
            "Calling infrastructure powered by Knowlarity — bundled in price."
        ),
        "monthly_price": 4999.0,
        "quarterly_price": 4499.0,
        "annual_price": 3999.0,
        "extra_user_price": 4999.0,
        "currency": "INR",
        "max_users": 10000,
        "max_admins": 100, "max_managers": 100,
        "max_team_leads": 100, "max_employees": 100,
        "storage_limit_gb": 50,
        "recording_retention_days": 365,
        "priority_support": True,
        "api_access": True,
        "display_order": 22,
        "setup_charges": 0.0,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "trial_days": 0,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#a855f7",
        "plan_badge": "Unlimited Calling",
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": False,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        "_features": BUSINESS_FEATURES,
    },
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        from app.models.plan import Plan
        from app.models.feature import Feature
        from app.models.plan_feature import PlanFeature

        feat_res = await db.execute(
            select(Feature).where(Feature.is_deleted == False)
        )
        all_features = {f.code: f for f in feat_res.scalars().all()}
        print(f"Found {len(all_features)} features in DB\n")

        for data in PLANS:
            feature_codes = data.pop("_features")

            existing = await db.execute(
                select(Plan).where(Plan.name == data["name"], Plan.is_deleted == False)
            )
            if existing.scalar_one_or_none():
                print(f"  '{data['name']}' already exists — skipping")
                data["_features"] = feature_codes
                continue

            plan = Plan(**data)
            db.add(plan)
            await db.flush()

            enabled_count = 0
            for code in feature_codes:
                feat = all_features.get(code)
                if feat:
                    db.add(PlanFeature(plan_id=plan.id, feature_id=feat.id, enabled=True))
                    enabled_count += 1
                else:
                    print(f"    WARNING: feature '{code}' not found in DB")

            print(f"  Created '{data['display_name']}' (₹{data['monthly_price']:,.0f}/seat) with {enabled_count} features")
            data["_features"] = feature_codes

        await db.commit()
        print("\nDone.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

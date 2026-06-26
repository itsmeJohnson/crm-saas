"""
Seed script: create/update plans to match CRM Commercial Proposal.
Run: docker compose exec backend python seed_plans.py

Plans (from PDF):
  Starter:    ₹3,999/seat/mo  | ₹11,499 qtr  | ₹44,999 annual | ₹50,000 setup
  Growth:     ₹4,999/seat/mo  | ₹13,999 qtr  | ₹53,999 annual | ₹75,000 setup
  Enterprise: ₹5,999/seat/mo  | ₹16,999 qtr  | ₹64,999 annual | ₹1,00,000 setup
"""

import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from sqlalchemy import select

PLANS = [
    {
        "name": "Starter",
        "monthly_price": 3999.0,
        "quarterly_price": 11499.0,
        "annual_price": 44999.0,
        "setup_charges": 50000.0,
        "max_users": 50,
        "description": "Essential CRM for growing teams. Includes Lead & Contact Management, Click-to-Call, Call Recording, Basic Pipeline, and more.",
    },
    {
        "name": "Growth",
        "monthly_price": 4999.0,
        "quarterly_price": 13999.0,
        "annual_price": 53999.0,
        "setup_charges": 75000.0,
        "max_users": 200,
        "description": "Advanced CRM with team management, KPI analytics, and target tracking. Recommended for scaling sales teams.",
    },
    {
        "name": "Enterprise",
        "monthly_price": 5999.0,
        "quarterly_price": 16999.0,
        "annual_price": 64999.0,
        "setup_charges": 100000.0,
        "max_users": 9999,
        "description": "Full-featured enterprise CRM with AI capabilities, custom reports, API access, and dedicated account management.",
    },
]

# Feature codes per plan (cumulative)
PLAN_FEATURES = {
    "starter": [
        "LEAD_MANAGEMENT",
        "CONTACT_MANAGEMENT",
        "FOLLOW_UP_TASKS",
        "CLICK_TO_CALL",
        "INBOUND_CALLING",
        "OUTBOUND_CALLING",
        "CALL_RECORDING",
        "SALES_PIPELINE",
        "BULK_IMPORT",
        "DASHBOARD_REPORTS",
        "ROLE_BASED_ACCESS",
    ],
    "growth": [
        "LEAD_MANAGEMENT",
        "CONTACT_MANAGEMENT",
        "FOLLOW_UP_TASKS",
        "CLICK_TO_CALL",
        "INBOUND_CALLING",
        "OUTBOUND_CALLING",
        "CALL_RECORDING",
        "SALES_PIPELINE",
        "BULK_IMPORT",
        "DASHBOARD_REPORTS",
        "ROLE_BASED_ACCESS",
        "GOOGLE_SHEETS_IMPORT",
        "CUSTOM_PIPELINE",
        "LEAD_DISTRIBUTION",
        "TEAM_LEADER_DASHBOARD",
        "KPI_DASHBOARD",
        "TARGET_MANAGEMENT",
        "MANAGER_DASHBOARD",
        "PRIORITY_SUPPORT",
        "ADVANCED_PIPELINE",
        "LEAD_TRANSFERS",
    ],
    "enterprise": [
        "LEAD_MANAGEMENT",
        "CONTACT_MANAGEMENT",
        "FOLLOW_UP_TASKS",
        "CLICK_TO_CALL",
        "INBOUND_CALLING",
        "OUTBOUND_CALLING",
        "CALL_RECORDING",
        "SALES_PIPELINE",
        "BULK_IMPORT",
        "DASHBOARD_REPORTS",
        "ROLE_BASED_ACCESS",
        "GOOGLE_SHEETS_IMPORT",
        "CUSTOM_PIPELINE",
        "LEAD_DISTRIBUTION",
        "TEAM_LEADER_DASHBOARD",
        "KPI_DASHBOARD",
        "TARGET_MANAGEMENT",
        "MANAGER_DASHBOARD",
        "PRIORITY_SUPPORT",
        "ADVANCED_PIPELINE",
        "LEAD_TRANSFERS",
        "AI_CALL_SUMMARY",
        "AI_FOLLOW_UP",
        "ADVANCED_ANALYTICS",
        "API_ACCESS",
        "CUSTOM_REPORTS",
    ],
}


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Migrate old "professional" plan name to "growth" ──
        await db.execute(text("UPDATE plans SET name='Growth' WHERE LOWER(name)='professional'"))
        await db.commit()

        for plan_data in PLANS:
            name = plan_data["name"]
            result = await db.execute(select(Plan).where(Plan.name == name))
            plan = result.scalar_one_or_none()

            if plan is None:
                plan = Plan(**plan_data, plan_active=True)
                db.add(plan)
                await db.flush()
                print(f"  Created plan: {name}")
            else:
                plan.monthly_price = plan_data["monthly_price"]
                plan.quarterly_price = plan_data["quarterly_price"]
                plan.annual_price = plan_data["annual_price"]
                plan.setup_charges = plan_data["setup_charges"]
                plan.max_users = plan_data["max_users"]
                plan.description = plan_data["description"]
                plan.plan_active = True
                print(f"  Updated plan: {name}")

            # ── Sync plan features ──
            feature_codes = PLAN_FEATURES.get(name.lower(), [])
            for code in feature_codes:
                feat_result = await db.execute(select(Feature).where(Feature.code == code))
                feature = feat_result.scalar_one_or_none()
                if feature is None:
                    feature = Feature(code=code, display_name=code.replace("_", " ").title(), category="crm", active=True)
                    db.add(feature)
                    await db.flush()

                pf_result = await db.execute(
                    select(PlanFeature).where(PlanFeature.plan_id == plan.id, PlanFeature.feature_id == feature.id)
                )
                if pf_result.scalar_one_or_none() is None:
                    db.add(PlanFeature(plan_id=plan.id, feature_id=feature.id, is_enabled=True))

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())

"""
Seed three "No Calling" plan variants.

Pricing rationale (Indian CRM SaaS market):
  Removing integrated telephony (Click-to-Call / Inbound / Outbound / Recording)
  saves infra cost and suits teams that use external dialer software.
  Discount: ~₹1,500 per plan.

  Starter Basic (No Calling):    ₹2,499 / seat / month
  Growth  Basic (No Calling):    ₹3,499 / seat / month
  Enterprise Basic (No Calling): ₹4,499 / seat / month
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/crm",
)

# Calling-related feature codes excluded from these plans
CALLING_CODES = {
    "CALL_DISPOSITION",
    "CALL_RECORDING",
    "CLICK_TO_CALL",
    "INBOUND_CALLING",
    "OUTBOUND_CALLING",
    "AI_CALL_SUMMARY",
}

NO_CALLING_PLANS = [
    {
        "name": "StarterBasic",
        "display_name": "Starter Basic",
        "description": "Essential CRM for growing teams — without integrated calling. Connect your own dialer or use external telephony.",
        "monthly_price": 2499.0,
        "quarterly_price": 2249.0,
        "annual_price": 1999.0,
        "extra_user_price": 2499.0,
        "currency": "INR",
        "max_users": 50,
        "max_admins": 100,
        "max_managers": 100,
        "max_team_leads": 100,
        "max_employees": 100,
        "storage_limit_gb": 10,
        "recording_retention_days": 0,   # no call recording
        "priority_support": False,
        "api_access": False,
        "display_order": 10,
        "setup_charges": 0.0,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "trial_days": 0,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#6366f1",
        "plan_badge": "No Calling",
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": True,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        # parent plan name to copy features from (minus calling)
        "_copy_from": "Starter",
    },
    {
        "name": "GrowthBasic",
        "display_name": "Growth Basic",
        "description": "Advanced CRM with team management, KPI analytics, and target tracking — without integrated calling.",
        "monthly_price": 3499.0,
        "quarterly_price": 3149.0,
        "annual_price": 2799.0,
        "extra_user_price": 3499.0,
        "currency": "INR",
        "max_users": 500,
        "max_admins": 100,
        "max_managers": 100,
        "max_team_leads": 100,
        "max_employees": 100,
        "storage_limit_gb": 10,
        "recording_retention_days": 0,
        "priority_support": True,
        "api_access": False,
        "display_order": 11,
        "setup_charges": 0.0,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "trial_days": 0,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#8b5cf6",
        "plan_badge": "No Calling",
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": True,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        "_copy_from": "Growth",
    },
    {
        "name": "EnterpriseBasic",
        "display_name": "Enterprise Basic",
        "description": "Full-featured enterprise CRM with AI, custom reports, and API access — without integrated calling.",
        "monthly_price": 4499.0,
        "quarterly_price": 4049.0,
        "annual_price": 3599.0,
        "extra_user_price": 4499.0,
        "currency": "INR",
        "max_users": 10000,
        "max_admins": 100,
        "max_managers": 100,
        "max_team_leads": 100,
        "max_employees": 100,
        "storage_limit_gb": 10,
        "recording_retention_days": 0,
        "priority_support": True,
        "api_access": True,
        "display_order": 12,
        "setup_charges": 0.0,
        "minimum_users": 10,
        "maximum_users": 1000,
        "minimum_contract_months": 3,
        "trial_days": 0,
        "discount_percentage": 0.0,
        "gst_percentage": 18.0,
        "plan_color": "#a855f7",
        "plan_badge": "No Calling",
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": True,
        "allow_additional_seats": True,
        "auto_renew": True,
        "plan_active": True,
        "_copy_from": "Enterprise",
    },
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        from app.models.plan import Plan
        from app.models.feature import Feature
        from app.models.plan_feature import PlanFeature

        # Fetch all features once
        features_res = await db.execute(select(Feature).where(Feature.is_deleted == False))
        all_features = {f.code: f for f in features_res.scalars().all()}
        print(f"Found {len(all_features)} features in DB")

        for plan_data in NO_CALLING_PLANS:
            copy_from = plan_data.pop("_copy_from")

            # Check if plan already exists
            existing = await db.execute(
                select(Plan).where(Plan.name == plan_data["name"], Plan.is_deleted == False)
            )
            existing_plan = existing.scalar_one_or_none()
            if existing_plan:
                print(f"  Plan '{plan_data['name']}' already exists — skipping")
                plan_data["_copy_from"] = copy_from
                continue

            # Get source plan's enabled features
            src_res = await db.execute(
                select(Plan).where(Plan.name == copy_from, Plan.is_deleted == False)
            )
            src_plan = src_res.scalar_one_or_none()
            if not src_plan:
                print(f"  WARNING: source plan '{copy_from}' not found")
                src_enabled_codes = set()
            else:
                pf_res = await db.execute(
                    select(PlanFeature).where(
                        PlanFeature.plan_id == src_plan.id,
                        PlanFeature.is_deleted == False,
                        PlanFeature.enabled == True,
                    )
                )
                src_mappings = pf_res.scalars().all()
                src_feat_ids = {m.feature_id for m in src_mappings}
                src_enabled_codes = {
                    code for code, feat in all_features.items()
                    if feat.id in src_feat_ids
                }

            # Create new plan
            new_plan = Plan(**plan_data)
            db.add(new_plan)
            await db.flush()  # get new_plan.id

            # Build feature mappings: copy source enabled features, skip calling codes
            enabled_codes = src_enabled_codes - CALLING_CODES
            for code in enabled_codes:
                feat = all_features.get(code)
                if feat:
                    db.add(PlanFeature(plan_id=new_plan.id, feature_id=feat.id, enabled=True))

            print(f"  Created plan '{plan_data['name']}' with {len(enabled_codes)} features (no calling)")
            plan_data["_copy_from"] = copy_from

        await db.commit()
        print("\nDone.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

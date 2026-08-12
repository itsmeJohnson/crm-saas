"""
Seed script: authoritative 4-tier plan/feature catalog.
Run: docker compose exec backend python seed_plans.py

Tiers (per seat / month, INR). Prices are adjustable later from the
SuperAdmin Control Center (Plans + Plan-Features toggle).

  Starter      Rs.1,499/seat/mo  | manual leads, basic pipeline
  Growth       Rs.2,999/seat/mo  | + bulk import, teams, calling, messaging
  Professional Rs.4,499/seat/mo  | + LEAD CAPTURE connectors, AI, analytics  (TRIAL PLAN)
  Enterprise   Rs.6,999/seat/mo  | + white-label branding, API access

This script is idempotent AND authoritative: for each plan it enables the
listed features and DISABLES any others, so re-running converges the catalog
to exactly this definition (existing tenants keep their subscription rows).
"""

import asyncio
from sqlalchemy import select

# Launch promotional discount applied to every plan (0.30 = 30% off).
PROMO_DISCOUNT = 0.30
from app.core.database import async_session_maker
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature

# ── Plan definitions ──────────────────────────────────────────────────────
PLANS = [
    {
        "name": "Starter", "display_order": 1,
        "monthly_price": 1499.0, "quarterly_price": 4299.0, "annual_price": 15299.0,
        "setup_charges": 0.0, "max_users": 50, "minimum_users": 3, "maximum_users": 50,
        "is_trial": False, "trial_days": None,
        "description": "Essential CRM for solo clinics & small teams. Manual lead & contact management, follow-ups, basic pipeline, click-to-call.",
    },
    {
        "name": "Growth", "display_order": 2,
        "monthly_price": 2999.0, "quarterly_price": 8599.0, "annual_price": 30599.0,
        "setup_charges": 0.0, "max_users": 200, "minimum_users": 5, "maximum_users": 200,
        "is_trial": False, "trial_days": None,
        "description": "Scaling teams: bulk import, roles & teams, custom pipelines, auto-distribution, calling, SMS/Email/WhatsApp, KPI & manager dashboards.",
    },
    {
        "name": "Professional", "display_order": 3,
        "monthly_price": 4499.0, "quarterly_price": 12899.0, "annual_price": 45899.0,
        "setup_charges": 25000.0, "max_users": 500, "minimum_users": 10, "maximum_users": 500,
        "is_trial": True, "trial_days": 14,
        "description": "Full sales engine: automatic Lead Capture from Google/Instagram/Facebook/webhooks, AI call summary & follow-up, advanced analytics, custom reports, priority support. (Free-trial plan.)",
    },
    {
        "name": "Enterprise", "display_order": 4,
        "monthly_price": 6999.0, "quarterly_price": 19999.0, "annual_price": 71399.0,
        "setup_charges": 75000.0, "max_users": 9999, "minimum_users": 10, "maximum_users": 9999,
        "is_trial": False, "trial_days": None,
        "description": "Everything in Professional plus white-label branding, API access, dedicated SLA/account manager. Custom domain & dedicated hosting available as a white-glove setup.",
    },
]

# ── Feature allocation (cumulative up the ladder) ─────────────────────────
STARTER = [
    "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "FOLLOW_UP_TASKS",
    "SALES_PIPELINE", "CLICK_TO_CALL", "BASIC_DASHBOARD", "DASHBOARD_REPORTS",
]
GROWTH = STARTER + [
    "BULK_IMPORT", "GOOGLE_SHEETS_IMPORT", "BULK_ASSIGNMENT",
    "ROLE_BASED_ACCESS", "CUSTOM_PIPELINE", "LEAD_DISTRIBUTION",
    "KPI_DASHBOARD", "TARGET_MANAGEMENT", "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD",
    "CALL_RECORDING", "INBOUND_CALLING", "OUTBOUND_CALLING",
    "SMS_MESSAGING", "EMAIL_MESSAGING", "WHATSAPP_MESSAGING", "CAMPAIGN_MANAGEMENT",
]
PROFESSIONAL = GROWTH + [
    "LEAD_CAPTURE", "ADVANCED_PIPELINE", "LEAD_TRANSFERS", "BULK_TRANSFER",
    "SMART_DISTRIBUTION", "TEAM_MONITORING", "CALL_DISPOSITION",
    "AI_CALL_SUMMARY", "AI_FOLLOW_UP", "ADVANCED_ANALYTICS",
    "CONVERSION_ANALYTICS", "CUSTOM_REPORTS", "PRIORITY_SUPPORT",
]
ENTERPRISE = PROFESSIONAL + [
    "WHITE_LABEL", "API_ACCESS",
]

PLAN_FEATURES = {
    "starter": STARTER,
    "growth": GROWTH,
    "professional": PROFESSIONAL,
    "enterprise": ENTERPRISE,
}

# Human-friendly names/categories for the two features this restructure adds.
FEATURE_META = {
    "LEAD_CAPTURE": ("Lead Capture Connectors", "Leads"),
    "WHITE_LABEL": ("White-Label Branding", "Platform"),
}


async def seed():
    async with async_session_maker() as db:
        for plan_data in PLANS:
            name = plan_data["name"]
            plan = (await db.execute(select(Plan).where(Plan.name == name))).scalar_one_or_none()
            fields = dict(
                display_name=name,
                monthly_price=plan_data["monthly_price"],
                quarterly_price=plan_data["quarterly_price"],
                annual_price=plan_data["annual_price"],
                price_inr=plan_data["monthly_price"],
                price_per_seat=plan_data["monthly_price"],
                # Launch offer: 30% off, shown as struck-through original + promo price.
                promo_price=round(plan_data["monthly_price"] * (1 - PROMO_DISCOUNT), 2),
                discount_percentage=PROMO_DISCOUNT * 100,
                setup_charges=plan_data["setup_charges"],
                max_users=plan_data["max_users"],
                minimum_users=plan_data["minimum_users"],
                maximum_users=plan_data["maximum_users"],
                description=plan_data["description"],
                display_order=plan_data["display_order"],
                is_trial=plan_data["is_trial"],
                trial_days=plan_data["trial_days"],
                allow_trial=plan_data["is_trial"],
                plan_active=True,
            )
            if plan is None:
                plan = Plan(name=name, **fields)
                db.add(plan)
                await db.flush()
                print(f"  Created plan: {name}")
            else:
                for k, v in fields.items():
                    setattr(plan, k, v)
                print(f"  Updated plan: {name}")

            desired = set(PLAN_FEATURES[name.lower()])

            # Ensure every desired feature exists, then enable its mapping.
            for code in desired:
                feature = (await db.execute(select(Feature).where(Feature.code == code))).scalar_one_or_none()
                if feature is None:
                    disp, cat = FEATURE_META.get(code, (code.replace("_", " ").title(), "crm"))
                    feature = Feature(code=code, display_name=disp, category=cat, active=True)
                    db.add(feature)
                    await db.flush()
                pf = (await db.execute(select(PlanFeature).where(
                    PlanFeature.plan_id == plan.id, PlanFeature.feature_id == feature.id
                ))).scalar_one_or_none()
                if pf is None:
                    db.add(PlanFeature(plan_id=plan.id, feature_id=feature.id, enabled=True))
                elif not pf.enabled:
                    pf.enabled = True

            # Authoritative: disable any enabled mapping NOT in the desired set.
            existing = (await db.execute(
                select(PlanFeature, Feature.code)
                .join(Feature, Feature.id == PlanFeature.feature_id)
                .where(PlanFeature.plan_id == plan.id, PlanFeature.enabled == True)
            )).all()
            for pf, code in existing:
                if code not in desired:
                    pf.enabled = False
                    print(f"    - disabled {code} on {name}")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())

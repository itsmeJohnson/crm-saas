"""
Seed script: authoritative 3-tier (+ Custom) plan/feature catalog.
Run: docker compose exec backend python seed_plans.py

Pricing is on TWO independent axes:
  • Seats  = how many telecallers  -> per-seat price, minimum 3 seats
  • Tier   = which capabilities    -> the feature bundle below

Tiers (per seat / month, INR):
  Connect   Rs.699/seat/mo   | Call, track, follow up (telecalling essentials)
  Convert   Rs.1,299/seat/mo | + auto-distribution, recording, campaigns, voice broadcast, manager analytics   (POPULAR / trial)
  Scale     Rs.1,999/seat/mo | + AI call summaries, advanced analytics, API, priority support
  Custom    (Enterprise)     | Everything + white-label, custom objects/verticals, KYC/bank APIs, dedicated SLA — contact sales

This script is idempotent AND authoritative:
  • It creates/updates exactly the four plans below (Connect/Convert/Scale/Enterprise).
  • For each plan it enables the listed features and DISABLES any others.
  • It SOFT-DELETES + deactivates every other plan (old Starter/Growth/Professional/etc.)
    so the catalog converges to exactly this definition.

NOTE: any tenant currently subscribed to a removed plan will lose feature access
until re-subscribed to one of the new plans (SuperAdmin -> Tenant -> Subscription).
"""

import asyncio
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature

# Launch promotional discount applied to every plan (0.0 = no promo; clean prices).
PROMO_DISCOUNT = 0.0
# Discounts baked into the longer billing cycles (off the per-seat monthly rate).
QUARTERLY_DISCOUNT = 0.05   # 5% off for 3-month commitment
ANNUAL_DISCOUNT = 0.15      # 15% off for 12-month commitment

# ── Plan definitions (per-seat monthly rate; quarterly/annual computed below) ──
PLANS = [
    {
        "name": "Connect", "display_order": 1,
        "monthly_price": 699.0,
        "setup_charges": 0.0, "max_users": 25, "minimum_users": 3, "maximum_users": 25,
        "is_trial": False, "trial_days": None,
        "popular_plan": False, "plan_badge": None,
        "description": "Telecalling essentials: leads, click-to-call with dispositions, follow-ups & reminders, WhatsApp + SMS, and a basic dashboard. Everything a calling team needs to call, track and follow up.",
    },
    {
        "name": "Convert", "display_order": 2,
        "monthly_price": 1299.0,
        "setup_charges": 0.0, "max_users": 100, "minimum_users": 3, "maximum_users": 100,
        "is_trial": True, "trial_days": 7,
        "popular_plan": True, "plan_badge": "Most Popular",
        "description": "Everything in Connect plus automatic lead distribution, call recording, campaigns & voice broadcast, custom pipelines, and manager/conversion analytics. Automate the work and measure conversion. (7-day free trial.)",
    },
    {
        "name": "Scale", "display_order": 3,
        "monthly_price": 1999.0,
        "setup_charges": 0.0, "max_users": 500, "minimum_users": 3, "maximum_users": 500,
        "is_trial": False, "trial_days": None,
        "popular_plan": False, "plan_badge": None,
        "description": "Everything in Convert plus AI call summaries & follow-up, advanced analytics + custom reports, team monitoring, API access and priority support. For teams scaling their calling engine.",
    },
    {
        "name": "Enterprise", "display_order": 4,
        "monthly_price": 2999.0,  # starting-from; real deals are negotiated
        "setup_charges": 25000.0, "max_users": 9999, "minimum_users": 3, "maximum_users": 9999,
        "is_trial": False, "trial_days": None,
        "popular_plan": False, "plan_badge": "Custom",
        "description": "Custom pricing. Everything in Scale plus white-label branding, custom objects & verticals (e.g. loan lenders, recruitment/onboarding), KYC/bank-API integrations, dedicated onboarding and SLA. Contact sales.",
    },
]

# ── Feature allocation (cumulative up the ladder) ─────────────────────────
CONNECT = [
    "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "FOLLOW_UP_TASKS", "SALES_PIPELINE",
    "CLICK_TO_CALL", "OUTBOUND_CALLING", "CALL_DISPOSITION",
    "SMS_MESSAGING", "WHATSAPP_MESSAGING",
    "BASIC_DASHBOARD", "DASHBOARD_REPORTS", "ROLE_BASED_ACCESS", "BULK_IMPORT",
]
CONVERT = CONNECT + [
    "CALL_RECORDING", "INBOUND_CALLING",
    "LEAD_DISTRIBUTION", "SMART_DISTRIBUTION", "BULK_ASSIGNMENT",
    "CUSTOM_PIPELINE", "CAMPAIGN_MANAGEMENT", "VOICE_BROADCAST",
    "EMAIL_MESSAGING", "GOOGLE_SHEETS_IMPORT", "LEAD_CAPTURE",
    "KPI_DASHBOARD", "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD",
    "TARGET_MANAGEMENT", "CONVERSION_ANALYTICS",
]
SCALE = CONVERT + [
    "AI_CALL_SUMMARY", "AI_FOLLOW_UP",
    "ADVANCED_ANALYTICS", "CUSTOM_REPORTS", "ADVANCED_PIPELINE",
    "TEAM_MONITORING", "LEAD_TRANSFERS", "BULK_TRANSFER",
    "API_ACCESS", "PRIORITY_SUPPORT",
]
ENTERPRISE = SCALE + [
    "WHITE_LABEL",
]

PLAN_FEATURES = {
    "connect": CONNECT,
    "convert": CONVERT,
    "scale": SCALE,
    "enterprise": ENTERPRISE,
}

# Human-friendly names/categories for features that need nicer labels.
FEATURE_META = {
    "LEAD_CAPTURE": ("Lead Capture Connectors", "Leads"),
    "WHITE_LABEL": ("White-Label Branding", "Platform"),
    "VOICE_BROADCAST": ("Voice Broadcast (OBD/TTS)", "Communications"),
    "CALL_DISPOSITION": ("Call Dispositions", "Communications"),
}

_KEEP_PLAN_NAMES = {p["name"] for p in PLANS}


async def seed():
    async with async_session_maker() as db:
        for plan_data in PLANS:
            name = plan_data["name"]
            monthly = plan_data["monthly_price"]
            plan = (await db.execute(select(Plan).where(Plan.name == name))).scalar_one_or_none()
            fields = dict(
                display_name=name,
                monthly_price=monthly,
                quarterly_price=round(monthly * 3 * (1 - QUARTERLY_DISCOUNT), 2),
                annual_price=round(monthly * 12 * (1 - ANNUAL_DISCOUNT), 2),
                price_inr=monthly,
                price_per_seat=monthly,
                promo_price=round(monthly * (1 - PROMO_DISCOUNT), 2),
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
                popular_plan=plan_data.get("popular_plan", False),
                plan_badge=plan_data.get("plan_badge"),
                plan_active=True,
                is_deleted=False,
            )
            if plan is None:
                plan = Plan(name=name, **fields)
                db.add(plan)
                await db.flush()
                print(f"  Created plan: {name}  (Rs.{monthly:.0f}/seat/mo)")
            else:
                for k, v in fields.items():
                    setattr(plan, k, v)
                print(f"  Updated plan: {name}  (Rs.{monthly:.0f}/seat/mo)")

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

        # ── Remove all OTHER (legacy) plans from the catalog ──────────────────
        legacy = (await db.execute(select(Plan).where(
            Plan.name.notin_(_KEEP_PLAN_NAMES)
        ))).scalars().all()
        for old in legacy:
            if old.plan_active or not old.is_deleted:
                old.plan_active = False
                old.is_deleted = True
                # Also switch off its feature mappings so nothing leaks through.
                pfs = (await db.execute(select(PlanFeature).where(
                    PlanFeature.plan_id == old.id, PlanFeature.enabled == True
                ))).scalars().all()
                for pf in pfs:
                    pf.enabled = False
                print(f"  REMOVED legacy plan: {old.name} (deactivated + soft-deleted)")

        await db.commit()
        print("Seed complete. Catalog = Connect / Convert / Scale / Enterprise(Custom).")


if __name__ == "__main__":
    asyncio.run(seed())

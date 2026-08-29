"""
Seed script: authoritative 3-tier (+ Custom) plan/feature catalog.
Run: docker compose exec backend python seed_plans.py

Pricing is on TWO independent axes:
  • Seats  = how many telecallers  -> per-seat price, minimum 3 seats
  • Tier   = which capabilities    -> the feature bundle below

Agency Growth Platform - FLAT per-agency pricing (unlimited users), INR/month:
  Launch  Rs.9,999/mo  | 2,500 leads, 1 pipeline, CRM + email automation, basic analytics
  Growth  Rs.19,999/mo | 10,000 leads, multi-pipeline, advanced automation, UTM, campaigns/voice, advanced analytics, 2 sites  (POPULAR)
  Scale   Rs.34,999/mo | unlimited leads, AI summaries, full analytics, API, 5+ sites, white-label optional
billing_mode='flat' => invoice = monthly_price (seats ignored). lead_cap gates lead volume.

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
        "name": "Launch", "display_order": 1,
        "monthly_price": 9999.0, "billing_mode": "flat",
        "lead_cap": 2500, "website_limit": 1, "storage_limit_gb": 10, "recording_retention_days": 30,
        "setup_charges": 0.0, "max_users": 10, "minimum_users": 1, "maximum_users": 10,
        "is_trial": False, "trial_days": None,
        "popular_plan": False, "plan_badge": None,
        "description": "Agency Growth Platform - Launch. Up to 10 users, 2,500 leads, 1 pipeline, CRM + email automation, basic analytics. Everything to run your lead-to-close process in one place.",
    },
    {
        "name": "Growth", "display_order": 2,
        "monthly_price": 19999.0, "billing_mode": "flat",
        "lead_cap": 10000, "website_limit": 2, "storage_limit_gb": 25, "recording_retention_days": 90,
        "setup_charges": 0.0, "max_users": 30, "minimum_users": 1, "maximum_users": 30,
        "is_trial": False, "trial_days": None,
        "popular_plan": True, "plan_badge": "Most Popular",
        "description": "Agency Growth Platform - Growth. Up to 30 users, 10,000 leads, multiple pipelines, advanced automation & workflows, UTM attribution, lead scoring, campaigns & voice broadcast, advanced analytics, 2 websites, priority support.",
    },
    {
        "name": "Scale", "display_order": 3,
        "monthly_price": 34999.0, "billing_mode": "flat",
        "lead_cap": None, "website_limit": 5, "storage_limit_gb": 100, "recording_retention_days": 180,
        "setup_charges": 0.0, "max_users": 9999, "minimum_users": 1, "maximum_users": 9999,
        "is_trial": False, "trial_days": None,
        "popular_plan": False, "plan_badge": None,
        "description": "Agency Growth Platform - Scale. Unlimited users & leads, multiple pipelines, AI call summaries & follow-up, full analytics, API access, 5+ websites, custom workflows, white-label optional, priority support.",
    },
]

# ── Feature allocation (cumulative up the ladder) ─────────────────────────
LAUNCH = [
    "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "FOLLOW_UP_TASKS", "SALES_PIPELINE",
    "CLICK_TO_CALL", "OUTBOUND_CALLING", "CALL_DISPOSITION",
    "SMS_MESSAGING", "WHATSAPP_MESSAGING", "EMAIL_MESSAGING",
    "BASIC_DASHBOARD", "DASHBOARD_REPORTS", "ROLE_BASED_ACCESS", "BULK_IMPORT",
    "LEAD_CAPTURE",
]
GROWTH = LAUNCH + [
    "CALL_RECORDING", "INBOUND_CALLING",
    "LEAD_DISTRIBUTION", "SMART_DISTRIBUTION", "BULK_ASSIGNMENT",
    "CUSTOM_PIPELINE", "CAMPAIGN_MANAGEMENT", "VOICE_BROADCAST",
    "GOOGLE_SHEETS_IMPORT",
    "KPI_DASHBOARD", "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD",
    "TARGET_MANAGEMENT", "CONVERSION_ANALYTICS",
    "ADVANCED_ANALYTICS", "CUSTOM_REPORTS", "PRIORITY_SUPPORT",
]
SCALE = GROWTH + [
    "AI_CALL_SUMMARY", "AI_FOLLOW_UP", "ADVANCED_PIPELINE",
    "TEAM_MONITORING", "LEAD_TRANSFERS", "BULK_TRANSFER",
    "API_ACCESS", "WHITE_LABEL",
]

PLAN_FEATURES = {
    "launch": LAUNCH,
    "growth": GROWTH,
    "scale": SCALE,
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
                billing_mode=plan_data.get("billing_mode", "per_seat"),
                lead_cap=plan_data.get("lead_cap"),
                website_limit=plan_data.get("website_limit", 1),
                storage_limit_gb=plan_data.get("storage_limit_gb", 10),
                recording_retention_days=plan_data.get("recording_retention_days", 30),
                extra_user_price=0.0,
                allow_additional_seats=False,
                priority_support="PRIORITY_SUPPORT" in PLAN_FEATURES[plan_data["name"].lower()],
                api_access="API_ACCESS" in PLAN_FEATURES[plan_data["name"].lower()],
                plan_active=True,
                is_deleted=False,
            )
            unit = "/mo (flat, unlimited users)" if fields["billing_mode"] == "flat" else "/seat/mo"
            if plan is None:
                plan = Plan(name=name, **fields)
                db.add(plan)
                await db.flush()
                print(f"  Created plan: {name}  (Rs.{monthly:.0f}{unit})")
            else:
                for k, v in fields.items():
                    setattr(plan, k, v)
                print(f"  Updated plan: {name}  (Rs.{monthly:.0f}{unit})")

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

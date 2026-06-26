"""
patch_plan_prices.py — Update existing plan prices to correct INR values.
All prices are per user/month. GST 18% is added on top at invoice time.

Pricing:
  Starter:      ₹3,999/user/month  (10 users = ₹39,990 + GST)
  Professional: ₹4,999/user/month  (10 users = ₹49,990 + GST)
  Enterprise:   ₹7,999/user/month  (10 users = ₹79,990 + GST)

Usage:
    docker compose exec backend python patch_plan_prices.py
"""
import asyncio
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.plan import Plan

PRICE_MAP = {
    "starter": {
        "monthly_price": 3999.0,
        "quarterly_price": 11997.0,   # 3999 × 3
        "annual_price": 47988.0,      # 3999 × 12
        "price_per_seat": 3999.0,
        "price_inr": 3999.0,
        "extra_user_price": 3999.0,
        "gst_percentage": 18.0,
    },
    "professional": {
        "monthly_price": 4999.0,
        "quarterly_price": 14997.0,   # 4999 × 3
        "annual_price": 59988.0,      # 4999 × 12
        "price_per_seat": 4999.0,
        "price_inr": 4999.0,
        "extra_user_price": 4999.0,
        "gst_percentage": 18.0,
    },
    "enterprise": {
        "monthly_price": 7999.0,
        "quarterly_price": 23997.0,   # 7999 × 3
        "annual_price": 95988.0,      # 7999 × 12
        "price_per_seat": 7999.0,
        "price_inr": 7999.0,
        "extra_user_price": 7999.0,
        "gst_percentage": 18.0,
        "discount_percentage": 5.0,
    },
}

async def patch():
    async with async_session_maker() as session:
        plans = (await session.execute(select(Plan))).scalars().all()
        updated = 0
        for plan in plans:
            prices = PRICE_MAP.get(plan.name)
            if not prices:
                print(f"  ⚠ No price rule for plan '{plan.name}' — skipping")
                continue
            for field, value in prices.items():
                setattr(plan, field, value)
            updated += 1
            print(f"  ✅ Updated '{plan.name}': ₹{prices['monthly_price']:,.0f}/user/month")
        await session.commit()
        print(f"\n✅ Done — {updated} plan(s) updated")
        print("\nPricing summary (per user/month + 18% GST):")
        print("  Starter:       ₹3,999  → 10 users = ₹39,990 + ₹7,198 GST = ₹47,188")
        print("  Professional:  ₹4,999  → 10 users = ₹49,990 + ₹8,998 GST = ₹58,988")
        print("  Enterprise:    ₹7,999  → 10 users = ₹79,990 + ₹14,398 GST = ₹94,388")

if __name__ == "__main__":
    asyncio.run(patch())

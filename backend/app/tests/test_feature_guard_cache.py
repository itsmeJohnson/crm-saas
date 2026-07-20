import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.organization import Organization
from app.models.user import User
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.tenant_subscription import TenantSubscription
from app.core.security import create_access_token, get_password_hash
from app.core.redis import redis_client
from app.dependencies.feature_guard import invalidate_tenant_features, require_feature

@pytest.fixture
async def setup_feature_guard_data(db: AsyncSession):
    # 1. Create Org
    org = Organization(name="Cache Org", slug="cacheorg")
    db.add(org)
    await db.flush()

    # 2. Create Plan
    plan = Plan(
        name="Cached Plan",
        display_name="Cached Plan",
        description="Cached Plan description",
        price_inr=1000.0,
        billing_cycle_days=30,
        max_users=5,
        is_active=True
    )
    db.add(plan)
    await db.flush()

    # 3. Create Feature
    feat = Feature(
        code="VOIP_CALLS",
        display_name="VoIP Calling",
        category="Calling",
        active=True
    )
    db.add(feat)
    await db.flush()

    # 4. Map Plan to Feature
    pf = PlanFeature(
        plan_id=plan.id,
        feature_id=feat.id,
        enabled=True
    )
    db.add(pf)
    await db.flush()

    # 5. Create active subscription
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        users_purchased=0,
        billing_cycle="monthly",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(sub)
    await db.flush()

    # 6. Create User
    pwd_hash = get_password_hash("password123")
    user = User(
        organization_id=org.id,
        email="owner@cacheorg.com",
        hashed_password=pwd_hash,
        first_name="Cache",
        last_name="Owner",
        role="OrgAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    await db.flush()
    await db.commit()

    token = create_access_token(user.id)
    return {
        "org": org,
        "plan": plan,
        "feature": feat,
        "sub": sub,
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_feature_guard_cache_flow(setup_feature_guard_data: dict, db: AsyncSession):
    data = setup_feature_guard_data
    org_id = data["org"].id
    user = data["user"]
    cache_key = f"tenant_features:{org_id}"

    # Clean cache first
    await redis_client.delete(cache_key)

    # 1. Resolve dependency manually to trigger load
    dependency = require_feature("VOIP_CALLS")
    # Execute dependency logic
    await dependency(actor=user, db=db)

    # Verify cached data exists in Redis
    cached_val = await redis_client.get(cache_key)
    assert cached_val is not None
    features = json.loads(cached_val)
    assert "VOIP_CALLS" in features

    # 2. Modify DB (disable the plan feature mapping) to show caching works
    # If caching works, require_feature should still pass because it reads from cache
    stmt = select(PlanFeature).where(
        PlanFeature.plan_id == data["plan"].id,
        PlanFeature.feature_id == data["feature"].id
    )
    res = await db.execute(stmt)
    pf = res.scalar_one()
    pf.enabled = False
    await db.commit()

    # Re-run dependency -> should still pass (reads from cache)
    await dependency(actor=user, db=db)

    # 3. Invalidate cache manually
    await invalidate_tenant_features(org_id)

    # Cache should be deleted
    assert await redis_client.get(cache_key) is None

    # Re-run dependency -> should now raise 403 Forbidden (since cache is cleared and DB is enabled=False)
    with pytest.raises(HTTPException) as exc:
        await dependency(actor=user, db=db)
    assert exc.value.status_code == 403

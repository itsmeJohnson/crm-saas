import json
import logging
import uuid
from typing import Annotated
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan
from app.models.plan_feature import PlanFeature
from app.models.feature import Feature
from app.core.redis import redis_client

logger = logging.getLogger("feature_guard")

async def invalidate_tenant_features(org_id: str | uuid.UUID) -> None:
    """Invalidates cached active features list for a specific organization."""
    cache_key = f"tenant_features:{org_id}"
    await redis_client.delete(cache_key)

async def invalidate_all_tenant_features() -> None:
    """Invalidates all cached feature sets across all organizations."""
    await redis_client.delete_pattern("tenant_features:*")

async def get_active_features(db: AsyncSession, org_id: str | uuid.UUID) -> list[str]:
    """Returns the list of active feature codes for a tenant (Redis-cached 1h)."""
    cache_key = f"tenant_features:{org_id}"
    cached_val = await redis_client.get(cache_key)

    active_features = None
    if cached_val is not None:
        try:
            active_features = json.loads(cached_val)
        except Exception as e:
            logger.warning(f"Error decoding features cache for tenant {org_id}: {e}")

    if active_features is None:
        active_features = []
        stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == org_id,
            TenantSubscription.is_deleted == False
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()

        if sub:
            now = datetime.now(timezone.utc)
            if sub.status in ["active", "trial"] and (not sub.end_date or sub.end_date >= now):
                plan_stmt = select(Plan).where(Plan.id == sub.plan_id, Plan.is_active == True)
                plan_res = await db.execute(plan_stmt)
                plan = plan_res.scalar_one_or_none()
                if plan:
                    pf_stmt = (
                        select(Feature.code)
                        .join(PlanFeature, Feature.id == PlanFeature.feature_id)
                        .where(
                            PlanFeature.plan_id == plan.id,
                            PlanFeature.enabled == True,
                            Feature.active == True
                        )
                    )
                    pf_res = await db.execute(pf_stmt)
                    active_features = list(pf_res.scalars().all())

        await redis_client.set(cache_key, json.dumps(active_features), ex=3600)

    return active_features


async def tenant_has_feature(db: AsyncSession, actor: User, feature_code: str) -> bool:
    """Imperative feature check for use inside endpoints. SuperAdmin always passes."""
    if actor.role == "SuperAdmin":
        return True
    if not actor.organization_id:
        return False
    return feature_code in await get_active_features(db, actor.organization_id)


def require_feature(feature_code: str):
    async def dependency(
        actor: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ) -> None:
        # SuperAdmin has full bypass
        if actor.role == "SuperAdmin":
            return

        org_id = actor.organization_id
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

        active_features = await get_active_features(db, org_id)

        if feature_code not in active_features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

    return dependency

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

def require_feature(feature_code: str):
    async def dependency(
        actor: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ) -> None:
        # SuperAdmin has full bypass
        if actor.role == "SuperAdmin":
            return

        # Fetch tenant active subscription
        stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == actor.organization_id,
            TenantSubscription.is_deleted == False
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

        # Check subscription status and expiry
        now = datetime.now(timezone.utc)
        if sub.status not in ["active", "trial"] or (sub.end_date and sub.end_date < now):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

        # Fetch the plan to verify if active
        plan_stmt = select(Plan).where(Plan.id == sub.plan_id, Plan.is_active == True)
        plan_res = await db.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

        # Check if the feature mapping is enabled in the plan_features table
        pf_stmt = (
            select(PlanFeature)
            .join(Feature, Feature.id == PlanFeature.feature_id)
            .where(
                PlanFeature.plan_id == plan.id,
                Feature.code == feature_code,
                PlanFeature.enabled == True,
                Feature.active == True
            )
        )
        pf_res = await db.execute(pf_stmt)
        pf = pf_res.scalar_one_or_none()
        if not pf:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature Not Available"
            )

    return dependency

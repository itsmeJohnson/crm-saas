import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.permissions import require_active_user, require_role
from app.models.user import User
from app.schemas.analytics import (
    PerformanceTargetCreate,
    PerformanceTargetResponse,
    TelecallerMetricsResponse,
    TeamLeaderMetricsResponse,
    ManagerMetricsResponse,
    SuperAdminMetricsResponse,
    UnifiedDashboardResponse
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()

async def check_is_telecaller(user: User, db: AsyncSession) -> bool:
    if user.role != "Employee" or not user.reporting_to_id:
        return False
    parent_res = await db.execute(select(User.role).filter(User.id == user.reporting_to_id))
    parent_role = parent_res.scalar()
    return parent_role == "Employee"

async def check_is_team_leader(user: User, db: AsyncSession) -> bool:
    if user.role != "Employee" or not user.reporting_to_id:
        return False
    parent_res = await db.execute(select(User.role).filter(User.id == user.reporting_to_id))
    parent_role = parent_res.scalar()
    return parent_role == "Manager"

@router.get("/dashboard", response_model=UnifiedDashboardResponse)
async def get_unified_dashboard(
    target_date: Optional[date] = None,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the unified analytics dashboard based on the authenticated user's hierarchy level."""
    if not target_date:
        target_date = date.today()

    # 1. SuperAdmin / OrgAdmin
    if actor.role in ["SuperAdmin", "OrgAdmin"]:
        metrics = await AnalyticsService.get_super_admin_metrics(db, actor.organization_id, target_date)
        return UnifiedDashboardResponse(role="SuperAdmin", metrics=metrics)

    # 2. Manager
    if actor.role == "Manager":
        metrics = await AnalyticsService.get_manager_metrics(db, actor, target_date)
        return UnifiedDashboardResponse(role="Manager", metrics=metrics)

    # 3. Team Leader
    is_tl = await check_is_team_leader(actor, db)
    if is_tl:
        metrics = await AnalyticsService.get_team_leader_metrics(db, actor, target_date)
        return UnifiedDashboardResponse(role="TeamLeader", metrics=metrics)

    # 4. Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if is_tele:
        metrics = await AnalyticsService.get_telecaller_metrics(db, actor, target_date)
        return UnifiedDashboardResponse(role="Telecaller", metrics=metrics)

    # Fallback/Default
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access the analytics dashboard."
    )

@router.get("/telecaller", response_model=TelecallerMetricsResponse)
async def get_telecaller_metrics(
    target_date: Optional[date] = None,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get metrics for the calling telecaller."""
    # Guard: must be a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to access telecaller metrics."
        )

    if not target_date:
        target_date = date.today()

    return await AnalyticsService.get_telecaller_metrics(db, actor, target_date)

@router.get("/team-leader", response_model=TeamLeaderMetricsResponse)
async def get_team_leader_metrics(
    target_date: Optional[date] = None,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get downline metrics and performance rankings for the calling Team Leader."""
    # Guard: must be a Team Leader
    is_tl = await check_is_team_leader(actor, db)
    if not is_tl:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Team Leaders are allowed to access team leader metrics."
        )

    if not target_date:
        target_date = date.today()

    return await AnalyticsService.get_team_leader_metrics(db, actor, target_date)

@router.get("/manager", response_model=ManagerMetricsResponse)
async def get_manager_metrics(
    target_date: Optional[date] = None,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get TL team metrics for the calling Manager."""
    # Guard: must be a Manager
    if actor.role != "Manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Managers are allowed to access manager metrics."
        )

    if not target_date:
        target_date = date.today()

    return await AnalyticsService.get_manager_metrics(db, actor, target_date)

@router.get("/super-admin", response_model=SuperAdminMetricsResponse)
async def get_super_admin_metrics(
    target_date: Optional[date] = None,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get organizational target progress gauges for the calling Admin."""
    # Guard: must be OrgAdmin or SuperAdmin
    if actor.role not in ["OrgAdmin", "SuperAdmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins are allowed to access organizational analytics."
        )

    if not target_date:
        target_date = date.today()

    return await AnalyticsService.get_super_admin_metrics(db, actor.organization_id, target_date)

@router.post("/targets", response_model=PerformanceTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_performance_target(
    target_in: PerformanceTargetCreate,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new performance target (Admins only)."""
    if actor.role not in ["OrgAdmin", "SuperAdmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins are allowed to create performance targets."
        )

    return await AnalyticsService.create_target(db, actor.organization_id, target_in)

@router.get("/targets", response_model=List[PerformanceTargetResponse])
async def list_performance_targets(
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all performance targets (Admins only)."""
    if actor.role not in ["OrgAdmin", "SuperAdmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins are allowed to view performance targets."
        )

    return await AnalyticsService.list_targets(db, actor.organization_id)

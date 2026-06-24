from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse, RecentActivitiesResponse
from app.services.dashboard_service import DashboardService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.get("/summary", response_model=DashboardSummaryResponse, status_code=status.HTTP_200_OK)
async def get_dashboard_summary(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve summarized operational KPIs and metrics for the organization."""
    dashboard_service = DashboardService(db)
    return await dashboard_service.get_summary(actor)

@router.get("/recent-activities", response_model=RecentActivitiesResponse, status_code=status.HTTP_200_OK)
async def get_recent_activities(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """List recent activities in the organization in chronological order with pagination."""
    dashboard_service = DashboardService(db)
    return await dashboard_service.get_recent_activities(actor, page, limit)

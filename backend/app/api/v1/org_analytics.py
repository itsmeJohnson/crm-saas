from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.org_analytics import (
    OverviewResponse, HealthResponse, LeaderboardRow, HeatmapResponse, TrendResponse,
)
from app.services.org_analytics_service import OrganizationAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
async def overview(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await OrganizationAnalyticsService(db).overview(actor, date_from=date_from, date_to=date_to)


@router.get("/health", response_model=HealthResponse)
async def health(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await OrganizationAnalyticsService(db).health(actor)


@router.get("/leaderboard", response_model=List[LeaderboardRow])
async def leaderboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      metric: str = Query("sales_revenue"), date_from: date | None = Query(None),
                      date_to: date | None = Query(None), limit: int = Query(10, ge=1, le=50)):
    return await OrganizationAnalyticsService(db).leaderboard(actor, metric, date_from=date_from, date_to=date_to, limit=limit)


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await OrganizationAnalyticsService(db).heatmap(actor, date_from=date_from, date_to=date_to)


@router.get("/trend", response_model=TrendResponse)
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                granularity: str = Query("monthly"), count: int = Query(6, ge=1, le=24)):
    return await OrganizationAnalyticsService(db).trend(actor, granularity=granularity, count=count)


@router.get("/domain/{kind}", response_model=List[dict])
async def domain(kind: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await OrganizationAnalyticsService(db).domain(actor, kind, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    csv_text = await OrganizationAnalyticsService(db).export_csv(actor, date_from=date_from, date_to=date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=organization-analytics.csv"})

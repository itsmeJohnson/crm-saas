import uuid
from datetime import date, timedelta
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.performance import (
    KPICreate, KPIUpdate, KPIResponse, GoalCreate, GoalUpdate, GoalResponse,
    ScorecardResponse, TrendResponse, LeaderboardRow, AchievementRow, DashboardResponse,
    ReportResponse, SeedResult, EvaluateResult,
)
from app.services.performance_service import PerformanceService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _month_default(date_from, date_to):
    if date_to is None:
        date_to = date.today()
    if date_from is None:
        date_from = date_to.replace(day=1)
    return date_from, date_to


# ---------- Dashboard / scorecard / trends / leaderboard / report ----------
@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).dashboard(actor)


@router.get("/scorecard", response_model=ScorecardResponse)
async def scorecard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    user_id: uuid.UUID | None = Query(None), date_from: date | None = Query(None),
                    date_to: date | None = Query(None)):
    date_from, date_to = _month_default(date_from, date_to)
    return await PerformanceService(db).scorecard(actor, user_id or actor.id, date_from, date_to)


@router.get("/trend", response_model=TrendResponse)
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                user_id: uuid.UUID | None = Query(None), granularity: str = Query("weekly"),
                count: int = Query(8, ge=1, le=26), metric: str | None = Query(None)):
    return await PerformanceService(db).period_performance(actor, user_id or actor.id, granularity, count, metric=metric)


@router.get("/leaderboard", response_model=List[LeaderboardRow])
async def leaderboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      metric: str = Query("sales_revenue"), date_from: date | None = Query(None),
                      date_to: date | None = Query(None), limit: int = Query(20, ge=1, le=100)):
    date_from, date_to = _month_default(date_from, date_to)
    return await PerformanceService(db).leaderboard(actor, metric, date_from, date_to, limit=limit)


@router.get("/report", response_model=ReportResponse)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 date_from: date | None = Query(None), date_to: date | None = Query(None),
                 user_id: uuid.UUID | None = Query(None)):
    date_from, date_to = _month_default(date_from, date_to)
    return await PerformanceService(db).report(actor, date_from, date_to, user_id=user_id)


# ---------- KPIs ----------
@router.get("/kpis", response_model=List[KPIResponse])
async def list_kpis(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    status_filter: str | None = Query(None, alias="status")):
    return await PerformanceService(db).list_kpis(actor, status_filter=status_filter)


@router.post("/kpis", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(req: KPICreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).create_kpi(actor, req.model_dump())


@router.post("/kpis/seed", response_model=SeedResult)
async def seed_kpis(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).seed_default_kpis(actor)


@router.patch("/kpis/{kpi_id}", response_model=KPIResponse)
async def update_kpi(kpi_id: uuid.UUID, req: KPIUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).update_kpi(actor, kpi_id, req.model_dump(exclude_unset=True))


@router.delete("/kpis/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kpi(kpi_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await PerformanceService(db).delete_kpi(actor, kpi_id)


# ---------- Goals ----------
@router.get("/goals", response_model=List[GoalResponse])
async def list_goals(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     user_id: uuid.UUID | None = Query(None), status_filter: str | None = Query(None, alias="status")):
    return await PerformanceService(db).list_goals(actor, user_id=user_id, status_filter=status_filter)


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(req: GoalCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).create_goal(actor, req.model_dump())


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(goal_id: uuid.UUID, req: GoalUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).update_goal(actor, goal_id, req.model_dump(exclude_unset=True))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await PerformanceService(db).delete_goal(actor, goal_id)


# ---------- Achievements ----------
@router.get("/achievements", response_model=List[AchievementRow])
async def list_achievements(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                            user_id: uuid.UUID | None = Query(None)):
    return await PerformanceService(db).list_achievements(actor, user_id=user_id)


@router.post("/achievements/evaluate", response_model=EvaluateResult)
async def evaluate(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await PerformanceService(db).evaluate_achievements(actor)

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.user import User
from app.services.historical_analytics_service import HistoricalAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()


class SettingsUpdate(BaseModel):
    retention_days: int | None = Field(None, ge=30, le=3650)
    archive_enabled: bool | None = None
    capture_enabled: bool | None = None


def _svc(db):
    return HistoricalAnalyticsService(db)


@router.get("/meta")
async def meta(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).meta()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/trends")
async def trends(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 metric: str = Query(...), days: int = Query(90, ge=7, le=1460)):
    return await _svc(db).trends(actor, metric, days=days)


@router.get("/comparison")
async def comparison(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     period: str = Query("month")):
    return await _svc(db).comparison(actor, period)


@router.get("/rolling")
async def rolling(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  metric: str = Query(...), window: int = Query(30), days: int = Query(180, ge=7, le=1460)):
    return await _svc(db).rolling(actor, metric, window=window, days=days)


@router.get("/snapshots")
async def snapshots(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    snapshot_date: str | None = Query(None), metric: str | None = Query(None),
                    granularity: str | None = Query(None), limit: int = Query(200, ge=1, le=500)):
    return await _svc(db).snapshots(actor, snapshot_date=snapshot_date, metric=metric,
                                    granularity=granularity, limit=limit)


@router.post("/capture")
async def capture_now(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).capture_now(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 period: str = Query("month")):
    return await _svc(db).report(actor, period)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     kind: str = Query("comparison"), metric: str | None = Query(None),
                     period: str = Query("month"), days: int = Query(90, ge=7, le=1460)):
    return await _svc(db).export_csv(actor, kind=kind, metric=metric, period=period, days=days)


@router.get("/settings")
async def get_settings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_settings(actor)


@router.patch("/settings")
async def update_settings(req: SettingsUpdate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_settings(actor, req.model_dump(exclude_unset=True))

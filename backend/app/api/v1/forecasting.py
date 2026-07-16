from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.forecasting_service import ForecastingService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return ForecastingService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.get("/forecast")
async def forecast(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   metric: str = Query("revenue"), periods: int = Query(6, ge=1, le=36),
                   method: str = Query("linear"), granularity: str = Query("monthly")):
    return await _svc(db).forecast(actor, metric=metric, periods=periods, method=method, granularity=granularity)


@router.get("/scenario")
async def scenario(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   metric: str = Query("revenue"), periods: int = Query(6, ge=1, le=36),
                   method: str = Query("linear"), granularity: str = Query("monthly")):
    return await _svc(db).scenario_analysis(actor, metric=metric, periods=periods, method=method, granularity=granularity)


@router.get("/seasonality")
async def seasonality(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      metric: str = Query("revenue"), granularity: str = Query("monthly")):
    return await _svc(db).seasonality(actor, metric=metric, granularity=granularity)


@router.get("/trend")
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                metric: str = Query("revenue"), granularity: str = Query("monthly")):
    return await _svc(db).trend_analysis(actor, metric=metric, granularity=granularity)


@router.get("/historical-comparison")
async def historical_comparison(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                                metric: str = Query("revenue"), granularity: str = Query("monthly"), holdout: int = Query(3, ge=1, le=12)):
    return await _svc(db).historical_comparison(actor, metric=metric, granularity=granularity, holdout=holdout)


@router.get("/pipeline")
async def pipeline_forecast(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                            periods: int = Query(3, ge=1, le=12), granularity: str = Query("monthly")):
    return await _svc(db).pipeline_forecast(actor, periods=periods, granularity=granularity)


@router.get("/goals")
async def goal_forecast(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).goal_forecast(actor)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     metric: str = Query("revenue"), periods: int = Query(6, ge=1, le=36),
                     method: str = Query("linear"), granularity: str = Query("monthly")):
    csv_text = await _svc(db).export_csv(actor, metric=metric, periods=periods, method=method, granularity=granularity)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=forecast.csv"})

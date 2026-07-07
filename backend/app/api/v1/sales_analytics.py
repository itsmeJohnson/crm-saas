from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.sales_analytics_service import SalesAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()
Range = tuple  # noqa


def _svc(db):
    return SalesAnalyticsService(db)


@router.get("/overview")
async def overview(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).overview(actor, date_from, date_to)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/funnel")
async def funnel(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).funnel(actor, date_from, date_to)


@router.get("/conversion")
async def conversion(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).conversion(actor, date_from, date_to)


@router.get("/revenue")
async def revenue(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).revenue(actor, date_from, date_to)


@router.get("/sources")
async def source_roi(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).source_roi(actor, date_from, date_to)


@router.get("/lost-reasons")
async def lost_reasons(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                       date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).lost_reasons(actor, date_from, date_to)


@router.get("/velocity")
async def velocity(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).velocity_and_cycle(actor, date_from, date_to)


@router.get("/forecast")
async def forecast(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).forecast(actor, date_from, date_to)


@router.get("/trend")
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                granularity: str = Query("monthly"), date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).trend(actor, granularity=granularity, date_from=date_from, date_to=date_to)


@router.get("/heatmap")
async def heatmap(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).heatmap(actor, date_from, date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    csv_text = await _svc(db).export_csv(actor, date_from, date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=sales-analytics.csv"})

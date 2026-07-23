from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.ai_analytics_service import AIAnalyticsService

router = APIRouter()

_Days = Query(30, ge=1, le=365)


def _svc(db):
    return AIAnalyticsService(db)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).dashboard(actor, days)


@router.get("/overview")
async def overview(actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).overview(actor, days)


@router.get("/latency")
async def latency(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).latency(actor, days)


@router.get("/quality")
async def quality(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).quality(actor, days)


@router.get("/user-adoption")
async def user_adoption(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).user_adoption(actor, days)


@router.get("/feature-adoption")
async def feature_adoption(actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).feature_adoption(actor, days)


@router.get("/prompt-performance")
async def prompt_performance(actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).prompt_performance(actor, days)


@router.get("/model-performance")
async def model_performance(actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).model_performance(actor, days)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).report(actor, days)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)], days: int = _Days):
    return await _svc(db).export_csv(actor, days)

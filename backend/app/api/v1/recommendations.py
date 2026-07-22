import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.recommendation_engine_service import RecommendationEngineService

router = APIRouter()


class FeedbackRequest(BaseModel):
    action: str = Field(..., description="pending|accepted|dismissed|snoozed|completed")
    feedback_id: uuid.UUID | None = None
    rec_key: str | None = Field(None, max_length=200)
    rec_type: str | None = None
    title: str | None = Field(None, max_length=300)
    reason: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    payload: dict | None = None
    snooze_hours: int | None = Field(None, ge=1, le=720)


def _svc(db):
    return RecommendationEngineService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.get("/feed")
async def feed(actor: Annotated[User, Depends(require_active_user)],
               db: Annotated[AsyncSession, Depends(get_db)],
               limit: int = Query(25, ge=1, le=100)):
    return await _svc(db).feed(actor, limit=limit)


@router.get("/personalized")
async def personalized(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)],
                       limit: int = Query(25, ge=1, le=100)):
    return await _svc(db).personalized(actor, limit=limit)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/analytics")
async def analytics(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).analytics(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.post("/feedback")
async def feedback(req: FeedbackRequest, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).record_feedback(
        actor, action=req.action, feedback_id=req.feedback_id, rec_key=req.rec_key,
        rec_type=req.rec_type, title=req.title, reason=req.reason,
        target_type=req.target_type, target_id=req.target_id, payload=req.payload,
        snooze_hours=req.snooze_hours)


# ---- per-type recommendation endpoints ----
@router.get("/next-best-actions")
async def next_best_actions(actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)],
                            limit: int = Query(20, ge=1, le=100)):
    return await _svc(db).next_best_actions(actor, limit=limit)


@router.get("/follow-ups")
async def follow_ups(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     limit: int = Query(20, ge=1, le=100)):
    return await _svc(db).follow_ups(actor, limit=limit)


@router.get("/call-times")
async def call_times(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     limit: int = Query(10, ge=1, le=50)):
    return await _svc(db).call_times(actor, limit=limit)


@router.get("/agents")
async def agents(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 lead_id: uuid.UUID | None = Query(None), limit: int = Query(5, ge=1, le=25)):
    return await _svc(db).agents(actor, lead_id=lead_id, limit=limit)


@router.get("/products")
async def products(actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)],
                   limit: int = Query(20, ge=1, le=100)):
    return await _svc(db).products(actor, limit=limit)


@router.get("/workflows")
async def workflows(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)],
                    limit: int = Query(10, ge=1, le=50)):
    return await _svc(db).workflows(actor, limit=limit)


@router.get("/campaigns")
async def campaigns(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)],
                    limit: int = Query(10, ge=1, le=50)):
    return await _svc(db).campaigns(actor, limit=limit)


@router.get("/knowledge")
async def knowledge(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)],
                    q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=25)):
    return await _svc(db).knowledge(actor, q, limit=limit)

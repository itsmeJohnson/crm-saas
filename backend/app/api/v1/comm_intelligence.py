import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.comm_intelligence_service import CommIntelligenceService
from app.middleware.permissions import require_active_user

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str
    channel: str | None = None


class TranscriptRequest(BaseModel):
    transcript: str
    activity_id: uuid.UUID | None = None


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"


class MeetingRequest(BaseModel):
    notes: str | None = None
    transcript: str | None = None


def _svc(db):
    return CommIntelligenceService(db)


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).analyze(actor, req.model_dump())


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    days: int = Query(30, ge=1, le=365)):
    return await _svc(db).dashboard(actor, days=days)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 days: int = Query(30, ge=1, le=365)):
    return await _svc(db).report(actor, days=days)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     days: int = Query(30, ge=1, le=365)):
    return await _svc(db).export_csv(actor, days=days)


@router.post("/transcript")
async def analyze_transcript(req: TranscriptRequest, actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).analyze_transcript(actor, req.model_dump())


@router.post("/translate")
async def translate(req: TranslateRequest, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).translate(actor, req.model_dump())


@router.post("/meeting-summary")
async def meeting_summary(req: MeetingRequest, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).meeting_summary(actor, req.model_dump())


@router.get("/conversation")
async def conversation(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                       lead_id: uuid.UUID | None = Query(None), contact_id: uuid.UUID | None = Query(None)):
    return await _svc(db).conversation(actor, lead_id=lead_id, contact_id=contact_id)


@router.get("/activities/{activity_id}")
async def activity_intelligence(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                                db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).activity_intelligence(actor, activity_id)


@router.get("/activities/{activity_id}/summary")
async def activity_summary(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).activity_summary(actor, activity_id)

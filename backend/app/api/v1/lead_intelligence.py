import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.lead_intelligence_service import LeadIntelligenceService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return LeadIntelligenceService(db)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.get("/leads")
async def list_leads(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     temperature: str | None = Query(None), quality: str | None = Query(None),
                     sort: str = Query("opportunity"), limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).list_leads(actor, temperature=temperature, quality=quality, sort=sort, limit=limit)


@router.get("/leads/{lead_id}")
async def lead_intelligence(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).lead_intelligence(actor, lead_id)


@router.get("/leads/{lead_id}/summary")
async def lead_summary(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).lead_summary(actor, lead_id)


@router.get("/leads/{lead_id}/duplicates")
async def lead_duplicates(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).duplicates(actor, lead_id)

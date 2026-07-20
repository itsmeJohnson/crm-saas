import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.sales_intelligence_service import SalesIntelligenceService
from app.middleware.permissions import require_active_user

router = APIRouter()


class ObjectionRequest(BaseModel):
    objection: str


def _svc(db):
    return SalesIntelligenceService(db)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/pipeline-insights")
async def pipeline_insights(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).pipeline_insights(actor)


@router.get("/revenue-prediction")
async def revenue_prediction(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).revenue_prediction(actor)


@router.get("/competitor-analysis")
async def competitor_analysis(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).competitor_analysis(actor)


@router.get("/upsell")
async def upsell(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).upsell_suggestions(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.get("/deals")
async def list_deals(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     health: str | None = Query(None), sort: str = Query("expected_value"),
                     limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).list_deals(actor, health=health, sort=sort, limit=limit)


@router.get("/deals/{lead_id}")
async def deal_intelligence(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).deal_intelligence(actor, lead_id)


@router.get("/deals/{lead_id}/summary")
async def deal_summary(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).deal_summary(actor, lead_id)


@router.post("/deals/{lead_id}/coaching")
async def coaching(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).coaching(actor, lead_id)


@router.post("/deals/{lead_id}/objection-handling")
async def objection_handling(lead_id: uuid.UUID, req: ObjectionRequest,
                             actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).objection_handling(actor, lead_id, req.objection)


@router.post("/deals/{lead_id}/proposal")
async def proposal(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).proposal(actor, lead_id)


@router.post("/deals/{lead_id}/quotation")
async def quotation(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).quotation(actor, lead_id)

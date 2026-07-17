import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.predictive_service import PredictiveService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return PredictiveService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


# ---------- structured datasets & training exports ----------
@router.get("/datasets/{key}")
async def dataset(key: str, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)], limit: int = Query(500, ge=1, le=5000)):
    return await _svc(db).dataset(actor, key, limit=limit)


@router.get("/datasets/{key}/export")
async def export_dataset(key: str, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)], format: str = Query("csv")):
    content, mime, filename = await _svc(db).export_dataset(actor, key, fmt=format)
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---------- prediction APIs (heuristic_v1 — ai-ready contracts) ----------
@router.get("/predict/lead/{lead_id}")
async def predict_lead(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_lead(actor, lead_id)


@router.get("/predict/churn/{company_id}")
async def predict_churn(company_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_churn(actor, company_id)


@router.get("/predict/clv/{company_id}")
async def predict_clv(company_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      horizon_months: int = Query(12, ge=1, le=60)):
    return await _svc(db).predict_clv(actor, company_id, horizon_months=horizon_months)


@router.get("/predict/risk/{company_id}")
async def predict_risk(company_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_risk(actor, company_id)


@router.get("/predict/collection/{invoice_id}")
async def predict_collection(invoice_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_collection(actor, invoice_id)


@router.get("/predict/employee/{user_id}")
async def predict_employee(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_employee(actor, user_id)


@router.get("/recommendations")
async def recommendations(actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)],
                          scope: str = Query("all"), limit: int = Query(25, ge=1, le=100)):
    return await _svc(db).recommendations(actor, scope=scope, limit=limit)

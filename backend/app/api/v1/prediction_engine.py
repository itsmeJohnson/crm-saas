import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.prediction_engine_service import PredictionEngineService

router = APIRouter()


def _svc(db):
    return PredictionEngineService(db)


@router.get("/models")
async def models(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    svc._require_manager(actor)
    return svc.models()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.get("/accuracy")
async def accuracy(actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).forecast_accuracy(actor)


# ---- single-entity predictions ----
@router.get("/predict/lead/{lead_id}")
async def predict_lead(lead_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_lead(actor, lead_id)


@router.get("/predict/churn/{company_id}")
async def predict_churn(company_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_churn(actor, company_id)


@router.get("/predict/collection/{invoice_id}")
async def predict_collection(invoice_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_collection(actor, invoice_id)


@router.get("/predict/employee/{user_id}")
async def predict_employee(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_employee(actor, user_id)


@router.get("/predict/task/{task_id}")
async def predict_task(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_task(actor, task_id)


@router.get("/predict/campaign/{campaign_id}")
async def predict_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).predict_campaign(actor, campaign_id)


# ---- org-level predictions ----
@router.get("/predict/sales")
async def predict_sales(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)],
                        periods: int = Query(3, ge=1, le=24),
                        granularity: str = Query("monthly")):
    return await _svc(db).predict_sales(actor, periods=periods, granularity=granularity)


@router.get("/predict/revenue")
async def predict_revenue(actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)],
                          periods: int = Query(6, ge=1, le=24),
                          granularity: str = Query("monthly")):
    return await _svc(db).predict_revenue(actor, periods=periods, granularity=granularity)


@router.get("/predict/tasks")
async def task_delays(actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      limit: int = Query(50, ge=1, le=200)):
    return await _svc(db).task_delay_predictions(actor, limit=limit)


@router.get("/predict/campaigns")
async def campaign_preds(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)],
                         limit: int = Query(50, ge=1, le=200)):
    return await _svc(db).campaign_predictions(actor, limit=limit)

from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.automation_analytics import (
    OverviewResponse, WorkflowsResponse, QueueResponse, RuleUsageResponse, TopAutomationsResponse,
    SLAComplianceResponse, EscalationResponse, ApprovalResponse, TrendResponse, DashboardResponse,
)
from app.services.automation_analytics_service import AutomationAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
async def overview(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).overview(actor, date_from=date_from, date_to=date_to)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationAnalyticsService(db).dashboard(actor)


@router.get("/workflows", response_model=WorkflowsResponse)
async def workflows(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).workflows(actor, date_from=date_from, date_to=date_to)


@router.get("/queue", response_model=QueueResponse)
async def queue(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).queue(actor, date_from=date_from, date_to=date_to)


@router.get("/rules", response_model=RuleUsageResponse)
async def rule_usage(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).rule_usage(actor, date_from=date_from, date_to=date_to)


@router.get("/top", response_model=TopAutomationsResponse)
async def top_automations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          date_from: date | None = Query(None), date_to: date | None = Query(None),
                          limit: int = Query(10, ge=1, le=50)):
    return await AutomationAnalyticsService(db).top_automations(actor, date_from=date_from, date_to=date_to, limit=limit)


@router.get("/sla", response_model=SLAComplianceResponse)
async def sla_compliance(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).sla_compliance(actor, date_from=date_from, date_to=date_to)


@router.get("/escalation", response_model=EscalationResponse)
async def escalation_metrics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                             date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).escalation_metrics(actor, date_from=date_from, date_to=date_to)


@router.get("/approval", response_model=ApprovalResponse)
async def approval_metrics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                           date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).approval_metrics(actor, date_from=date_from, date_to=date_to)


@router.get("/trend", response_model=TrendResponse)
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                granularity: str = Query("daily"), date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await AutomationAnalyticsService(db).trend(actor, granularity=granularity, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    csv_text = await AutomationAnalyticsService(db).export_csv(actor, date_from=date_from, date_to=date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=automation-analytics.csv"})

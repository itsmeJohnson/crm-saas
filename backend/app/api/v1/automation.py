import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.automation import (
    JobResponse, EnableRequest, JobConfigRequest, RunResponse,
    SLACreate, SLAUpdate, SLAResponse, BreachResponse,
    ReportCreate, ReportUpdate, ScheduledReportResponse,
    AutomationReport, AutomationDashboard, SimpleResult,
)
from app.services.automation_service import AutomationService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / dashboard / report ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return AutomationService.catalog()


@router.get("/dashboard", response_model=AutomationDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).dashboard(actor)


@router.get("/report", response_model=AutomationReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).report(actor)


# ---------- jobs ----------
@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).list_jobs(actor)


@router.post("/jobs/sync", response_model=List[JobResponse])
async def sync_jobs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).sync_jobs(actor)


@router.post("/jobs/{job_key}/enable", response_model=JobResponse)
async def enable_job(job_key: str, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).set_job_enabled(actor, job_key, req.enabled)


@router.patch("/jobs/{job_key}", response_model=JobResponse)
async def config_job(job_key: str, req: JobConfigRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).set_job_config(actor, job_key, req.max_retries, req.schedule)


@router.post("/jobs/{job_key}/run", response_model=RunResponse)
async def run_job(job_key: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).run_job(actor, job_key)


# ---------- run history ----------
@router.get("/runs", response_model=List[RunResponse])
async def runs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
               job_key: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
               limit: int = Query(50, ge=1, le=200)):
    return await AutomationService(db).runs(actor, job_key=job_key, status_filter=status_filter, limit=limit)


@router.post("/runs/{run_id}/retry", response_model=RunResponse)
async def retry_run(run_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).retry_run(actor, run_id)


# ---------- SLA policies ----------
@router.get("/sla", response_model=List[SLAResponse])
async def list_sla(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).list_sla(actor)


@router.post("/sla", response_model=SLAResponse, status_code=status.HTTP_201_CREATED)
async def create_sla(req: SLACreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).create_sla(actor, req.model_dump())


@router.patch("/sla/{policy_id}", response_model=SLAResponse)
async def update_sla(policy_id: uuid.UUID, req: SLAUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).update_sla(actor, policy_id, req.model_dump(exclude_unset=True))


@router.delete("/sla/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sla(policy_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await AutomationService(db).delete_sla(actor, policy_id)


@router.get("/breaches", response_model=List[BreachResponse])
async def breaches(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   resolved: bool | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await AutomationService(db).list_breaches(actor, resolved=resolved, limit=limit)


@router.post("/breaches/{breach_id}/resolve", response_model=BreachResponse)
async def resolve_breach(breach_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).resolve_breach(actor, breach_id)


# ---------- scheduled reports ----------
@router.get("/reports", response_model=List[ScheduledReportResponse])
async def list_reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).list_reports(actor)


@router.post("/reports", response_model=ScheduledReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(req: ReportCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).create_report(actor, req.model_dump())


@router.patch("/reports/{report_id}", response_model=ScheduledReportResponse)
async def update_report(report_id: uuid.UUID, req: ReportUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).update_report(actor, report_id, req.model_dump(exclude_unset=True))


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await AutomationService(db).delete_report(actor, report_id)


@router.post("/reports/{report_id}/run", response_model=SimpleResult)
async def run_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AutomationService(db).run_report_now(actor, report_id)

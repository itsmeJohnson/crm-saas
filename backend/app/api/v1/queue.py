import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.queue import (
    EnqueueRequest, JobResponse, WorkerResponse, QueueDashboard, QueueReport, PurgeRequest, SimpleResult,
)
from app.services.queue_service import QueueService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return QueueService.catalog()


@router.get("/dashboard", response_model=QueueDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).dashboard(actor)


@router.get("/report", response_model=QueueReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).report(actor)


# ---------- jobs ----------
@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def enqueue(req: EnqueueRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).enqueue_api(actor, req.model_dump())


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    queue: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
                    scheduled: bool | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await QueueService(db).list_jobs(actor, queue=queue, status_filter=status_filter, scheduled=scheduled, limit=limit)


@router.get("/jobs/scheduled", response_model=List[JobResponse])
async def scheduled_jobs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         limit: int = Query(50, ge=1, le=200)):
    return await QueueService(db).list_jobs(actor, scheduled=True, limit=limit)


@router.get("/dead-letter", response_model=List[JobResponse])
async def dead_letter(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      limit: int = Query(50, ge=1, le=200)):
    return await QueueService(db).dead_letter(actor, limit=limit)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).get(actor, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).cancel(actor, job_id)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).retry(actor, job_id)


@router.post("/purge", response_model=SimpleResult)
async def purge(req: PurgeRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).purge(actor, req.status)


# ---------- workers ----------
@router.get("/workers", response_model=List[WorkerResponse])
async def workers(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await QueueService(db).list_workers(actor)

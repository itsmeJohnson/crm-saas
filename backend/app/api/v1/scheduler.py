import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.scheduler import (
    ScheduleCreate, ScheduleUpdate, ScheduleResponse, RunResponse, EnableRequest,
    SchedulerReport, SchedulerDashboard,
)
from app.services.scheduler_service import SchedulerService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return SchedulerService.catalog()


@router.get("/dashboard", response_model=SchedulerDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).dashboard(actor)


@router.get("/report", response_model=SchedulerReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).report(actor)


# ---------- runs (execution history) ----------
@router.get("/runs", response_model=List[RunResponse])
async def runs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
               schedule_id: uuid.UUID | None = Query(None), status_filter: str | None = Query(None, alias="status"),
               limit: int = Query(50, ge=1, le=200)):
    return await SchedulerService(db).runs(actor, schedule_id=schedule_id, status_filter=status_filter, limit=limit)


# ---------- CRUD ----------
@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         active_only: bool = Query(False)):
    return await SchedulerService(db).list_schedules(actor, active_only=active_only)


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(req: ScheduleCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).create(actor, req.model_dump())


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).get(actor, schedule_id)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: uuid.UUID, req: ScheduleUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).update(actor, schedule_id, req.model_dump(exclude_unset=True))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await SchedulerService(db).delete(actor, schedule_id)


@router.post("/{schedule_id}/enable", response_model=ScheduleResponse)
async def enable_schedule(schedule_id: uuid.UUID, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).set_enabled(actor, schedule_id, req.enabled)


@router.post("/{schedule_id}/run", response_model=RunResponse)
async def run_now(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SchedulerService(db).run_now(actor, schedule_id)


@router.get("/{schedule_id}/next-runs")
async def next_runs(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    count: int = Query(5, ge=1, le=20)):
    return {"next_runs": await SchedulerService(db).preview_next_runs(actor, schedule_id, count)}

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.scheduled_report import ScheduleCreate, ScheduleUpdate
from app.services.scheduled_report_service import ScheduledReportService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return ScheduledReportService(db)


@router.get("/meta")
async def meta(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).meta()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/history")
async def history(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  schedule_id: uuid.UUID | None = Query(None), limit: int = Query(100, ge=1, le=300)):
    return await _svc(db).history(actor, schedule_id=schedule_id, limit=limit)


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(delivery_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).retry_delivery(actor, delivery_id)


# ---------- schedules ----------
@router.get("")
async def list_schedules(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_schedules(actor)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_schedule(req: ScheduleCreate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create(actor, req.model_dump())


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: uuid.UUID, req: ScheduleUpdate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update(actor, schedule_id, req.model_dump(exclude_unset=True))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete(actor, schedule_id)


@router.post("/{schedule_id}/run")
async def run_now(schedule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).run_now(actor, schedule_id)

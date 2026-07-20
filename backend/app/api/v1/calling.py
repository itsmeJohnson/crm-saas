import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.calling import (
    CallHistoryResponse, CallItem, CallTagsUpdate, CallReportResponse, CallQueueResponse,
)
from app.services.calling_service import CallingService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("/history", response_model=CallHistoryResponse)
async def call_history(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    direction: str | None = Query(None), disposition: str | None = Query(None),
    agent_id: uuid.UUID | None = Query(None), call_status: str | None = Query(None, alias="status"),
    tag: str | None = Query(None), has_recording: bool | None = Query(None),
    missed_only: bool = Query(False), search: str | None = Query(None),
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """Call history (Call activities) with filters; scoped to own calls unless OrgAdmin/Manager.
    Also lazily sweeps stale in-progress inbound calls into Missed before querying."""
    service = CallingService(db)
    flagged = await service.detect_missed_calls(actor.organization_id)
    if flagged:
        await db.commit()
    return await service.history(
        actor, direction=direction, disposition=disposition, agent_id=agent_id, call_status=call_status,
        tag=tag, has_recording=has_recording, missed_only=missed_only, search=search,
        date_from=date_from, date_to=date_to, skip=skip, limit=limit)


@router.get("/reports", response_model=CallReportResponse)
async def call_reports(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
):
    """Call analytics: volume by direction/disposition/agent/day, avg duration, connect rate."""
    return await CallingService(db).reports(actor, date_from=date_from, date_to=date_to)


@router.get("/queue", response_model=CallQueueResponse)
async def call_queue(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Live queue monitor: pending New-lead queue depth + downline agents with their current call
    (Manager/TeamLeader/OrgAdmin only)."""
    return await CallingService(db).queue(actor)


@router.get("/tags", response_model=List[str])
async def list_call_tags(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Distinct tags used on calls visible to the caller (for filter dropdowns)."""
    return await CallingService(db).list_tags(actor)


@router.patch("/{activity_id}/tags", response_model=CallItem)
async def set_call_tags(
    activity_id: uuid.UUID, req: CallTagsUpdate,
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
):
    """Replace the tag list on a call."""
    item = await CallingService(db).set_tags(actor, activity_id, req.tags)
    await db.commit()
    return item

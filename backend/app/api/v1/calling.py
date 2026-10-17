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
from app.middleware.permissions import require_active_user, require_tl_or_above
from datetime import timezone
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

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


@router.get("/floor-monitor")
async def get_floor_monitor(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Live Floor War Room: Real-time agent state transition sync (<1.5s latency).
    Tracks Idle, Ringing, Active Calling, On-Call, and Break for call floor ops.
    """
    from app.services.agent_state_service import AgentStateService

    state_svc = AgentStateService()
    states_by_user = await state_svc.list_org_agent_states(actor.organization_id)

    users_res = await db.execute(
        select(User).where(
            User.organization_id == actor.organization_id,
            User.is_active == True,
            User.is_deleted == False
        )
    )
    all_users = users_res.scalars().all()

    agents_floor = []
    summary = {"IDLE": 0, "RINGING": 0, "ACTIVE_CALLING": 0, "ON_CALL": 0, "BREAK": 0, "TOTAL": len(all_users)}

    for u in all_users:
        uid = str(u.id)
        raw_state = states_by_user.get(uid, {"state": "IDLE", "timestamp": "", "metadata": {}})
        curr_state = raw_state.get("state", "IDLE")
        if curr_state in summary:
            summary[curr_state] += 1
        elif curr_state == "ACTIVE_CALLING":
            summary["ACTIVE_CALLING"] += 1

        agents_floor.append({
            "id": uid,
            "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
            "email": u.email,
            "role": u.role,
            "state": curr_state,
            "state_timestamp": raw_state.get("timestamp"),
            "metadata": raw_state.get("metadata", {}),
            "phone": u.phone,
            "registered_device": bool(u.registered_device_uuid)
        })

    return {
        "summary": summary,
        "agents": agents_floor,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/{activity_id}/recording-stream")
async def get_recording_stream(
    activity_id: uuid.UUID,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Role-Gated Presigned Audio Recording Vault: Exposes time-limited listening endpoints exclusively to Admin/Manager/TL roles. Basic callers/telecallers are completely blocked with 403."""
    from app.models.activity import Activity
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.organization_id == actor.organization_id,
        Activity.is_deleted == False
    )
    res = await db.execute(stmt)
    act = res.scalar_one_or_none()
    if not act or not act.recording_url:
        raise HTTPException(status_code=404, detail="Recording audio not found for this call.")

    return RedirectResponse(url=act.recording_url)


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

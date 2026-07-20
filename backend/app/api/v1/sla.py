import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.sla import (
    PolicyCreate, PolicyUpdate, PolicyResponse, TrackerResponse, BreachResponse, EnableRequest,
    PauseRequest, ScanResult, SLAReport, SLADashboard,
)
from app.services.sla_service import SLAService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return SLAService.catalog()


@router.get("/dashboard", response_model=SLADashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).dashboard(actor)


@router.get("/report", response_model=SLAReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).report(actor)


# ---------- policies ----------
@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).list_policies(actor)


@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(req: PolicyCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).create_policy(actor, req.model_dump())


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(policy_id: uuid.UUID, req: PolicyUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).update_policy(actor, policy_id, req.model_dump(exclude_unset=True))


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await SLAService(db).delete_policy(actor, policy_id)


@router.post("/policies/{policy_id}/enable", response_model=PolicyResponse)
async def enable_policy(policy_id: uuid.UUID, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).set_enabled(actor, policy_id, req.enabled)


# ---------- trackers (active SLAs) ----------
@router.get("/trackers", response_model=List[TrackerResponse])
async def trackers(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   status_filter: str | None = Query(None, alias="status"), breached: bool | None = Query(None),
                   limit: int = Query(50, ge=1, le=200)):
    return await SLAService(db).trackers(actor, status_filter=status_filter, breached=breached, limit=limit)


@router.post("/trackers/{tracker_id}/pause", response_model=TrackerResponse)
async def pause_tracker(tracker_id: uuid.UUID, req: PauseRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).pause(actor, tracker_id, reason=req.reason)


@router.post("/trackers/{tracker_id}/resume", response_model=TrackerResponse)
async def resume_tracker(tracker_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await SLAService(db).resume(actor, tracker_id)


# ---------- breaches / scan ----------
@router.get("/breaches", response_model=List[BreachResponse])
async def breaches(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   resolved: bool | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await SLAService(db).breaches(actor, resolved=resolved, limit=limit)


@router.post("/scan", response_model=ScanResult)
async def scan_now(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return {"breaches": await SLAService(db).scan(actor.organization_id)}

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.voice import (
    VoiceSendRequest, VoiceBroadcastItem, VoiceBroadcastDetail, VoiceBroadcastList,
    MissedCallRequest,
)
from app.services.voice_service import VoiceService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import get_active_features

router = APIRouter()

# Voice broadcasting is entitled by the dedicated VOICE_BROADCAST feature, but we
# also honour SMS_MESSAGING so tenants already on the SMS/BulkSMSPlans plan keep
# working before the plan catalog is re-seeded with the new feature.
VOICE_FEATURES = ("VOICE_BROADCAST", "SMS_MESSAGING")


async def _require_feature(actor: User, db: AsyncSession):
    if actor.role == "SuperAdmin":
        return
    active = await get_active_features(db, actor.organization_id) if actor.organization_id else []
    if not any(f in active for f in VOICE_FEATURES):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Voice broadcasting is not included in your plan.")


# ---------- Broadcasts ----------
@router.post("/broadcasts", response_model=VoiceBroadcastDetail, status_code=status.HTTP_201_CREATED)
async def send_broadcast(req: VoiceSendRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create and dispatch a bulk voice broadcast (OBD voice note or TTS)."""
    await _require_feature(actor, db)
    service = VoiceService(db)
    bc = await service.create_and_send(actor, req.model_dump())
    return service.detail(bc)


@router.get("/broadcasts", response_model=VoiceBroadcastList)
async def list_broadcasts(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """List voice broadcasts (most recent first)."""
    return await VoiceService(db).list(actor, skip=skip, limit=limit)


@router.get("/broadcasts/{broadcast_id}", response_model=VoiceBroadcastDetail)
async def get_broadcast(broadcast_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Fetch a broadcast with its per-number delivery records."""
    service = VoiceService(db)
    return service.detail(await service.get(actor, broadcast_id))


@router.post("/broadcasts/{broadcast_id}/refresh", response_model=VoiceBroadcastDetail)
async def refresh_broadcast(broadcast_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Re-poll the vendor voice DLR and update per-number delivery statuses."""
    await _require_feature(actor, db)
    service = VoiceService(db)
    return service.detail(await service.refresh_dlr(actor, broadcast_id))


# ---------- Voice media ----------
@router.get("/media")
async def list_media(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """List the account's uploaded voice medias (live from the vendor)."""
    await _require_feature(actor, db)
    return await VoiceService(db).list_media(actor)


@router.post("/media")
async def upload_media(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    title: str = Form(...), vendor_account_id: str = Form(...), duration: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a voice-media file (mp3/wav) to the vendor account."""
    await _require_feature(actor, db)
    data = await file.read()
    return await VoiceService(db).upload_media(
        actor, title=title, vendor_account_id=vendor_account_id, duration=duration,
        file_bytes=data, filename=file.filename or "voice.mp3",
        content_type=file.content_type or "audio/mpeg")


# ---------- Missed-call alerts ----------
@router.post("/missed-calls")
async def missed_calls(req: MissedCallRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Fetch missed-call alert records for a DID over a date range."""
    await _require_feature(actor, db)
    return await VoiceService(db).missed_call_report(
        actor, did_number=req.did_number, start_date=req.start_date, end_date=req.end_date)

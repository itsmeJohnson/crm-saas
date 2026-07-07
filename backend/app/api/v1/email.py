import base64
import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.email import (
    EmailSettingsResponse, EmailSettingsUpdate, OAuthConnectRequest, EmailSendRequest, EmailReplyRequest,
    EmailForwardRequest, DraftCreate, DraftUpdate, EmailItem, EmailListResponse, ThreadSummary,
    ThreadDetail, EmailReportResponse, SyncResponse,
)
from app.services.email_service_module import EmailModuleService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import tenant_has_feature

router = APIRouter()

EMAIL_FEATURE = "EMAIL_MESSAGING"

# 1x1 transparent GIF for the open-tracking pixel
_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


async def _require_feature(actor: User, db: AsyncSession):
    if not await tenant_has_feature(db, actor, EMAIL_FEATURE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email integration is not included in your plan.")


# ---------- Settings ----------
@router.get("/settings", response_model=EmailSettingsResponse)
async def get_settings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view email settings.")
    return await EmailModuleService(db).get_settings(actor, create=True)


@router.put("/settings", response_model=EmailSettingsResponse)
async def update_settings(req: EmailSettingsUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailModuleService(db).update_settings(actor, req.model_dump(exclude_unset=True))


@router.post("/oauth/connect", response_model=EmailSettingsResponse)
async def oauth_connect(req: OAuthConnectRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Store OAuth tokens for a Gmail / Microsoft 365 mailbox (OrgAdmin)."""
    return await EmailModuleService(db).oauth_connect(actor, req.model_dump())


# ---------- Sending ----------
@router.post("/send", response_model=EmailItem, status_code=status.HTTP_201_CREATED)
async def send_email(req: EmailSendRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    service = EmailModuleService(db)
    act = await service.send(actor, req.model_dump())
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


@router.post("/{activity_id}/reply", response_model=EmailItem, status_code=status.HTTP_201_CREATED)
async def reply_email(activity_id: uuid.UUID, req: EmailReplyRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    service = EmailModuleService(db)
    act = await service.reply(actor, activity_id, req.model_dump())
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


@router.post("/{activity_id}/forward", response_model=EmailItem, status_code=status.HTTP_201_CREATED)
async def forward_email(activity_id: uuid.UUID, req: EmailForwardRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    service = EmailModuleService(db)
    act = await service.forward(actor, activity_id, req.model_dump())
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


# ---------- Drafts ----------
@router.post("/drafts", response_model=EmailItem, status_code=status.HTTP_201_CREATED)
async def create_draft(req: DraftCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    service = EmailModuleService(db)
    act = await service.create_draft(actor, req.model_dump())
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


@router.patch("/drafts/{activity_id}", response_model=EmailItem)
async def update_draft(activity_id: uuid.UUID, req: DraftUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    service = EmailModuleService(db)
    act = await service.update_draft(actor, activity_id, req.model_dump(exclude_unset=True))
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


@router.post("/drafts/{activity_id}/send", response_model=EmailItem)
async def send_draft(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    service = EmailModuleService(db)
    act = await service.send_draft(actor, activity_id)
    return service._item(act, await service._names({act.assigned_user_id or act.created_by}))


@router.delete("/drafts/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await EmailModuleService(db).delete_draft(actor, activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Folders / threads ----------
@router.get("/messages", response_model=EmailListResponse)
async def list_messages(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    folder: str = Query("inbox", pattern="^(inbox|sent|drafts|all)$"), search: str | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """List emails in a folder (inbox / sent / drafts / all), scoped to your mail unless OrgAdmin/Manager."""
    return await EmailModuleService(db).messages(actor, folder=folder, search=search, skip=skip, limit=limit)


@router.get("/threads", response_model=List[ThreadSummary])
async def list_threads(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """Threaded conversations grouped by email thread."""
    return await EmailModuleService(db).threads(actor, search=search, skip=skip, limit=limit)


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def thread_detail(thread_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailModuleService(db).thread_detail(actor, thread_id)


# ---------- Sync + reports ----------
@router.post("/sync", response_model=SyncResponse)
async def sync_inbox(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Pull new inbound mail via IMAP now (OrgAdmin/Manager)."""
    if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to trigger a mailbox sync.")
    n = await EmailModuleService(db).sync_inbox(actor.organization_id)
    return {"ingested": n}


@router.get("/reports", response_model=EmailReportResponse)
async def reports(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
):
    """Email analytics: sent/received/failed/drafts, open + click rates, by status/direction/day."""
    return await EmailModuleService(db).reports(actor, date_from=date_from, date_to=date_to)


# ---------- Public tracking (no auth) ----------
@router.get("/track/open/{tracking_id}")
async def track_open(tracking_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """Open-tracking pixel: records the open and returns a 1x1 GIF."""
    try:
        await EmailModuleService(db).record_open(tracking_id)
    except Exception:
        pass  # tracking must never fail the pixel load
    return Response(content=_PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, private"})


@router.get("/track/click/{tracking_id}")
async def track_click(tracking_id: str, db: Annotated[AsyncSession, Depends(get_db)], u: str = Query(...)):
    """Click-tracking redirect: records the click and 302s to the original URL."""
    try:
        await EmailModuleService(db).record_click(tracking_id)
    except Exception:
        pass
    return RedirectResponse(url=u, status_code=status.HTTP_302_FOUND)

import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Form, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.whatsapp import (
    WaSettingsResponse, WaSettingsUpdate, WaSendTextRequest, WaSendTemplateRequest,
    WaMessageItem, WaConversationItem, WaThreadResponse, WaAssignRequest,
    QuickReplyCreate, QuickReplyResponse, WaReportResponse, WaStatusWebhook, WaInboundWebhook,
)
from app.services.whatsapp_service import WhatsAppService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import tenant_has_feature

router = APIRouter()

WA_FEATURE = "WHATSAPP_MESSAGING"

# extension → WhatsApp media category
_IMAGE = {"jpg", "jpeg", "png", "webp"}
_VIDEO = {"mp4", "3gp"}
_AUDIO = {"ogg", "mp3", "aac", "amr", "m4a"}
_ALLOWED_MEDIA = _IMAGE | _VIDEO | _AUDIO | {"pdf", "docx", "xlsx", "csv"}


def _media_type_for(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext in _IMAGE:
        return "image"
    if ext in _VIDEO:
        return "video"
    if ext in _AUDIO:
        return "audio"
    return "document"


async def _require_feature(actor: User, db: AsyncSession):
    if not await tenant_has_feature(db, actor, WA_FEATURE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="WhatsApp messaging is not included in your plan.")


def _serialize(service: WhatsAppService, act) -> dict:
    return service._msg_item(act)


# ---------- Settings ----------
@router.get("/settings", response_model=WaSettingsResponse)
async def get_settings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view WhatsApp settings.")
    return await WhatsAppService(db).get_settings(actor, create=True)


@router.put("/settings", response_model=WaSettingsResponse)
async def update_settings(req: WaSettingsUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WhatsAppService(db).update_settings(actor, req.model_dump(exclude_unset=True))


# ---------- Sending ----------
@router.post("/send", response_model=WaMessageItem, status_code=status.HTTP_201_CREATED)
async def send_text(req: WaSendTextRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send a free-form WhatsApp text (requires an open 24h customer window)."""
    await _require_feature(actor, db)
    service = WhatsAppService(db)
    act = await service.send_text(actor, req.model_dump())
    return service._msg_item(act)


@router.post("/send-template", response_model=WaMessageItem, status_code=status.HTTP_201_CREATED)
async def send_template(req: WaSendTemplateRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send an approved template message (allowed even when the 24h window is closed)."""
    await _require_feature(actor, db)
    service = WhatsAppService(db)
    act = await service.send_template(actor, req.model_dump())
    return service._msg_item(act)


@router.post("/send-media", response_model=WaMessageItem, status_code=status.HTTP_201_CREATED)
async def send_media(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None), to_number: str | None = Form(None),
    lead_id: str | None = Form(None), contact_id: str | None = Form(None), caption: str | None = Form(None),
):
    """Upload and send a media message (image / video / document / voice note)."""
    await _require_feature(actor, db)
    from app.core.storage import validate_and_sanitize_file, get_storage_provider
    MAX_UPLOAD = 16 * 1024 * 1024  # WhatsApp media cap
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 16.0MB")
    try:
        sanitized, ext = validate_and_sanitize_file(content=content, filename=file.filename or "media",
                                                    allowed_extensions=_ALLOWED_MEDIA)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    url = await get_storage_provider().upload_file(content, sanitized)
    service = WhatsAppService(db)
    act = await service.send_media(actor, {
        "media_url": url, "media_type": _media_type_for(ext), "caption": caption, "filename": file.filename,
        "conversation_id": uuid.UUID(conversation_id) if conversation_id else None,
        "to_number": to_number, "lead_id": uuid.UUID(lead_id) if lead_id else None,
        "contact_id": uuid.UUID(contact_id) if contact_id else None,
    })
    return service._msg_item(act)


# ---------- Conversations ----------
@router.get("/conversations", response_model=List[WaConversationItem])
async def list_conversations(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"), assigned_to: uuid.UUID | None = Query(None),
    search: str | None = Query(None), unread_only: bool = Query(False),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """WhatsApp conversations (scoped to conversations assigned to you unless OrgAdmin/Manager)."""
    return await WhatsAppService(db).list_conversations(actor, status_filter=status_filter, assigned_to=assigned_to,
                                                        search=search, unread_only=unread_only, skip=skip, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=WaThreadResponse)
async def get_thread(conversation_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Full message thread for a conversation; marks it read."""
    return await WhatsAppService(db).thread(actor, conversation_id)


@router.post("/conversations/{conversation_id}/assign", response_model=WaConversationItem)
async def assign_conversation(conversation_id: uuid.UUID, req: WaAssignRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Assign (or unassign) a conversation to an agent (Manager/OrgAdmin)."""
    return await WhatsAppService(db).assign(actor, conversation_id, req.user_id)


# ---------- Quick replies ----------
@router.get("/quick-replies", response_model=List[QuickReplyResponse])
async def list_quick_replies(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await WhatsAppService(db).list_quick_replies(actor))


@router.post("/quick-replies", response_model=QuickReplyResponse, status_code=status.HTTP_201_CREATED)
async def create_quick_reply(req: QuickReplyCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WhatsAppService(db).create_quick_reply(actor, req.model_dump())


@router.delete("/quick-replies/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quick_reply(qr_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await WhatsAppService(db).delete_quick_reply(actor, qr_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Reports ----------
@router.get("/reports", response_model=WaReportResponse)
async def reports(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
):
    """WhatsApp analytics: delivered/read/failed/inbound, delivery + read rates, by status/direction/media/day."""
    return await WhatsAppService(db).reports(actor, date_from=date_from, date_to=date_to)


# ---------- Webhooks (token-secured; no auth dependency) ----------
@router.get("/webhook")
async def verify_webhook(
    db: Annotated[AsyncSession, Depends(get_db)],
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Meta subscription verification handshake — echoes hub.challenge when the verify token matches."""
    challenge = await WhatsAppService(db).verify_webhook(hub_verify_token, hub_challenge)
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhook/status", status_code=status.HTTP_200_OK)
async def status_webhook(payload: WaStatusWebhook, db: Annotated[AsyncSession, Depends(get_db)]):
    """Delivery / read receipt callback. Authenticated by the per-org webhook token."""
    return await WhatsAppService(db).handle_status(payload.token, payload.message_id, payload.status)


@router.post("/webhook/inbound", status_code=status.HTTP_200_OK)
async def inbound_webhook(payload: WaInboundWebhook, db: Annotated[AsyncSession, Depends(get_db)]):
    """Inbound message callback. Token-authenticated; matches a lead/contact, opens the
    24h window, notifies the owner, runs auto-reply, and fires workflow rules."""
    return await WhatsAppService(db).handle_inbound(payload.token, payload.from_number, payload.body,
                                                    payload.message_id, payload.media_type, payload.media_url)

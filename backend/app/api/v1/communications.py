import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.communication import (
    CommunicationLog, CommunicationItem, ConversationSummary, CommunicationStats,
    TemplateCreate, TemplateUpdate, TemplateResponse, TemplateRenderRequest, TemplateRenderResponse,
    CommAttachmentResponse,
)
from app.services.communication_service import CommunicationService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Log ----------
@router.post("/", response_model=CommunicationItem, status_code=status.HTTP_201_CREATED)
async def log_communication(req: CommunicationLog, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Log a communication (Call/SMS/WhatsApp/Email/Note) against a lead/contact/company."""
    return await CommunicationService(db).log(actor, req.model_dump())


# ---------- Feed ----------
@router.get("/", response_model=List[CommunicationItem])
async def communication_feed(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    lead_id: uuid.UUID | None = Query(None), contact_id: uuid.UUID | None = Query(None), company_id: uuid.UUID | None = Query(None),
    channel: str | None = Query(None), direction: str | None = Query(None), search: str | None = Query(None),
    unread_only: bool = Query(False), pinned_only: bool = Query(False), include_notes: bool = Query(True),
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
):
    """Unified communication feed across all channels, with search / filters / pin / unread."""
    return await CommunicationService(db).feed(
        actor, lead_id=lead_id, contact_id=contact_id, company_id=company_id, channel=channel, direction=direction,
        search=search, unread_only=unread_only, pinned_only=pinned_only, include_notes=include_notes,
        date_from=date_from, date_to=date_to, skip=skip, limit=limit)


@router.get("/conversations", response_model=List[ConversationSummary])
async def conversations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)], search: str | None = Query(None)):
    """Recent conversations grouped by customer/contact/company (sidebar) with unread counts."""
    return await CommunicationService(db).conversations(actor, search=search)


@router.get("/stats", response_model=CommunicationStats)
async def communication_stats(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationService(db).stats(actor)


# ---------- Read / pin ----------
@router.post("/read-all")
async def mark_all_read(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: uuid.UUID | None = Query(None), company_id: uuid.UUID | None = Query(None), lead_id: uuid.UUID | None = Query(None),
):
    n = await CommunicationService(db).mark_all_read(actor, contact_id=contact_id, company_id=company_id, lead_id=lead_id)
    return {"marked_read": n}


@router.post("/{activity_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CommunicationService(db).mark_read(actor, activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{activity_id}/pin")
async def toggle_pin(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    pinned = await CommunicationService(db).toggle_pin(actor, activity_id)
    return {"pinned": pinned}


# ---------- Attachments ----------
@router.get("/{activity_id}/attachments", response_model=List[CommAttachmentResponse])
async def list_attachments(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationService(db).list_attachments(actor, activity_id)


@router.post("/{activity_id}/attachments", response_model=CommAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)], file: UploadFile = File(...)):
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    return await CommunicationService(db).add_attachment(actor, activity_id, content, file.filename or "attachment")


@router.delete("/{activity_id}/attachments/{stored_name}")
async def delete_attachment(activity_id: uuid.UUID, stored_name: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationService(db).delete_attachment(actor, activity_id, stored_name)


# ---------- Templates ----------
@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await CommunicationService(db).list_templates(actor))


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(req: TemplateCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationService(db).create_template(actor, req.model_dump())


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: uuid.UUID, req: TemplateUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationService(db).update_template(actor, template_id, req.model_dump(exclude_unset=True))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CommunicationService(db).delete_template(actor, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/templates/{template_id}/render", response_model=TemplateRenderResponse)
async def render_template(template_id: uuid.UUID, req: TemplateRenderRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Render a template with a contact/company/lead's data substituted for {{placeholders}}."""
    return await CommunicationService(db).render_template(actor, template_id, req.model_dump())

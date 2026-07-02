import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notification_service import NotificationService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
):
    """List the current user's own notifications (never another user's, even within the same org)."""
    service = NotificationService(db)
    records, _ = await service.paginate_for_user(
        organization_id=actor.organization_id,
        user_id=actor.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    return list(records)

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = NotificationService(db)
    count = await service.get_unread_count(actor.organization_id, actor.id)
    return UnreadCountResponse(unread_count=count)

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = NotificationService(db)
    return await service.mark_read(actor.organization_id, actor.id, notification_id)

@router.post("/mark-all-read")
async def mark_all_notifications_read(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = NotificationService(db)
    count = await service.mark_all_read(actor.organization_id, actor.id)
    return {"marked_read": count}

import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse, UnreadCountResponse, CategoryCount, PreferenceItem, PreferenceUpdate,
    PushSubscribeReq, PushUnsubscribeReq, BulkReadReq, BroadcastReq, BroadcastResult, NotificationStats,
)
from app.services.notification_service import NotificationService, CATEGORIES
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (declared before /{id}) ----------
@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    count = await NotificationService(db).get_unread_count(actor.organization_id, actor.id)
    return UnreadCountResponse(unread_count=count)


@router.get("/unread-by-category", response_model=List[CategoryCount])
async def unread_by_category(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationService(db).unread_by_category(actor.organization_id, actor.id)


@router.get("/categories", response_model=List[str])
async def list_categories(actor: Annotated[User, Depends(require_active_user)]):
    return CATEGORIES


@router.get("/stats", response_model=NotificationStats)
async def notification_stats(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Notification analytics for the current user: totals, read rate, by category/priority."""
    return await NotificationService(db).stats(actor.organization_id, actor.id)


@router.get("/preferences", response_model=List[PreferenceItem])
async def get_preferences(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationService(db).get_preferences(actor)


@router.put("/preferences", response_model=List[PreferenceItem])
async def update_preferences(req: PreferenceUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await NotificationService(db).update_preferences(actor, [i.model_dump() for i in req.items])
    await db.commit()
    return result


@router.post("/push/subscribe")
async def push_subscribe(req: PushSubscribeReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    sub = await NotificationService(db).register_push(actor, req.model_dump())
    await db.commit()
    return {"id": str(sub.id)}


@router.post("/push/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def push_unsubscribe(req: PushUnsubscribeReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await NotificationService(db).unregister_push(actor, req.endpoint)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mark-all-read")
async def mark_all_read(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    count = await NotificationService(db).mark_all_read(actor.organization_id, actor.id)
    return {"marked_read": count}


@router.post("/bulk-read")
async def bulk_read(req: BulkReadReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Mark a set of notifications (by ids and/or category) read."""
    count = await NotificationService(db).bulk_read(actor.organization_id, actor.id, ids=req.ids, category=req.category)
    return {"marked_read": count}


@router.post("/broadcast", response_model=BroadcastResult)
async def broadcast(req: BroadcastReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send a notification to the whole org or a specific role (Manager/OrgAdmin)."""
    result = await NotificationService(db).broadcast(actor, req.model_dump())
    await db.commit()
    return result


# ---------- List / history ----------
@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False), category: str | None = Query(None), priority: str | None = Query(None),
    include_dismissed: bool = Query(False),
):
    """List the current user's own notifications (never another user's), with filters."""
    records, _ = await NotificationService(db).paginate_for_user(
        organization_id=actor.organization_id, user_id=actor.id, skip=skip, limit=limit,
        unread_only=unread_only, category=category, priority=priority, include_dismissed=include_dismissed)
    return list(records)


# ---------- Single ----------
@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(notification_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationService(db).mark_read(actor.organization_id, actor.id, notification_id)


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
async def dismiss_notification(notification_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationService(db).dismiss(actor.organization_id, actor.id, notification_id)

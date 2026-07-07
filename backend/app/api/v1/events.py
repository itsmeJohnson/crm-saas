import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.event import (
    EventResponse, DeliveryResponse, PublishCustomRequest, SubscriptionCreate, SubscriptionUpdate,
    SubscriptionResponse, EventStats, EventDashboard, RequeueResult,
)
from app.services.event_bus import EventBus
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return EventBus.catalog()


@router.get("/dashboard", response_model=EventDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).dashboard(actor)


@router.get("/stats", response_model=EventStats)
async def stats(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).stats(actor)


# ---------- publish (custom events) ----------
@router.post("/publish", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def publish_custom(req: PublishCustomRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    ev = await EventBus(db).publish_custom(actor, req.name, payload=req.payload,
                                           entity_type=req.entity_type, entity_id=req.entity_id)
    return EventBus(db)._event_dict(ev)


# ---------- event log / execution logs ----------
@router.get("/events", response_model=List[EventResponse])
async def list_events(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      event_type: str | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await EventBus(db).list_events(actor, event_type=event_type, limit=limit)


@router.get("/events/{event_id}/deliveries", response_model=List[DeliveryResponse])
async def event_deliveries(event_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).event_deliveries(actor, event_id)


# ---------- dead-letter queue ----------
@router.get("/dead-letter", response_model=List[DeliveryResponse])
async def dead_letter(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      limit: int = Query(50, ge=1, le=200)):
    return await EventBus(db).dead_letter_queue(actor, limit=limit)


@router.post("/deliveries/{delivery_id}/requeue", response_model=RequeueResult)
async def requeue(delivery_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).requeue(actor, delivery_id)


# ---------- subscriptions ----------
@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).list_subscriptions(actor)


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(req: SubscriptionCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).create_subscription(actor, req.model_dump())


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription(sub_id: uuid.UUID, req: SubscriptionUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EventBus(db).update_subscription(actor, sub_id, req.model_dump(exclude_unset=True))


@router.delete("/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(sub_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await EventBus(db).delete_subscription(actor, sub_id)

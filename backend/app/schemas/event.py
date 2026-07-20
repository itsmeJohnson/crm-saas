import uuid
from pydantic import BaseModel, Field


class EventResponse(BaseModel):
    id: str
    event_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    source: str
    status: str
    subscriber_count: int
    delivered_count: int
    failed_count: int
    duration_ms: int | None = None
    published_at: str | None = None


class DeliveryResponse(BaseModel):
    id: str
    event_id: str
    subscription_id: str | None = None
    subscriber: str
    event_type: str
    status: str
    attempts: int
    error: str | None = None
    duration_ms: int | None = None
    is_dead_letter: bool
    delivered_at: str | None = None


class PublishCustomRequest(BaseModel):
    name: str = Field(..., max_length=60)
    payload: dict | None = None
    entity_type: str | None = None
    entity_id: str | None = None


class SubscriptionCreate(BaseModel):
    name: str = Field(..., max_length=120)
    event_pattern: str = "*"
    subscriber_type: str = "webhook"
    config: dict | None = None
    is_active: bool = True
    max_attempts: int = 3


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    event_pattern: str | None = None
    subscriber_type: str | None = None
    config: dict | None = None
    is_active: bool | None = None
    max_attempts: int | None = None


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    event_pattern: str
    subscriber_type: str
    config: dict | None = None
    is_active: bool
    max_attempts: int
    delivered_count: int
    failed_count: int
    created_at: str | None = None


class EventStats(BaseModel):
    total_events: int
    deliveries: int
    failed_deliveries: int
    success_rate: float
    dead_letter: int
    avg_publish_ms: float
    by_type: dict


class EventDashboard(BaseModel):
    total_events: int
    success_rate: float
    dead_letter: int
    subscriptions: int
    recent: list[dict]


class RequeueResult(BaseModel):
    requeued: bool
    delivered: bool

"""Event Bus — decoupled, event-driven backbone.

Producers `publish` typed domain events without knowing who consumes them.
Subscribers (built-in code handlers + user-configured webhooks) are matched by
event-type pattern and delivered independently, with retry, a dead-letter queue,
per-delivery execution logs and monitoring.

Decoupling: the legacy `WorkflowService.run()` used to call
`WorkflowEngineService.dispatch()` directly. That single hook is replaced by a
bus publish; the workflow engine is now a *subscriber* (`workflow_engine`) that
the bus invokes — so it still runs exactly once (backward compatible), but the
producer no longer references the consumer, and new subscribers attach without
touching producers.

Delivery model: in-process handlers (workflow_engine) receive the LIVE entity
object; webhook subscribers receive the JSON `payload`. Everything is recorded
so the bus is observable and Redis/queue-backed delivery can be swapped in later
behind the same publish/subscribe API.
"""
from __future__ import annotations
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event, EventSubscription, EventDelivery

# Guard against event storms: handlers that create notifications / mutate rows
# must not recursively re-emit events while a publish is being delivered.
_dispatching: ContextVar[bool] = ContextVar("_event_bus_dispatching", default=False)

# ---- domain event catalog (families → concrete types) ----
EVENT_TYPES = {
    "lead": ["lead.created", "lead.updated", "lead.converted"],
    "task": ["task.created", "task.updated", "task.completed"],
    "communication": ["communication.call_logged", "communication.call_disposition",
                      "communication.sms_sent", "communication.sms_received",
                      "communication.whatsapp_sent", "communication.whatsapp_received",
                      "communication.email_sent", "communication.email_received"],
    "attendance": ["attendance.marked", "attendance.late_login"],
    "leave": ["leave.applied", "leave.approved"],
    "approval": ["approval.approved", "approval.rejected"],
    "invoice": ["invoice.created"],
    "payment": ["payment.received"],
    "notification": ["notification.created"],
    "user": ["user.created"],
    "shift": ["shift.assigned"],
    "performance": ["performance.goal_achieved"],
    "custom": ["custom.*"],
}
ALL_EVENT_TYPES = [t for group in EVENT_TYPES.values() for t in group]
EVENT_FAMILIES = list(EVENT_TYPES.keys())

# legacy WorkflowService trigger name → bus event type
TRIGGER_EVENT_MAP = {
    "lead_created": "lead.created", "lead_updated": "lead.updated", "lead_converted": "lead.converted",
    "task_created": "task.created", "task_updated": "task.updated", "task_completed": "task.completed",
    "call_logged": "communication.call_logged", "call_disposition": "communication.call_disposition",
    "sms_sent": "communication.sms_sent", "sms_received": "communication.sms_received",
    "whatsapp_sent": "communication.whatsapp_sent", "whatsapp_received": "communication.whatsapp_received",
    "email_sent": "communication.email_sent", "email_received": "communication.email_received",
    "attendance_marked": "attendance.marked", "late_login": "attendance.late_login",
    "leave_applied": "leave.applied", "leave_approved": "leave.approved",
    "approval_approved": "approval.approved", "approval_rejected": "approval.rejected",
    "invoice_created": "invoice.created", "payment_received": "payment.received",
    "user_created": "user.created", "shift_assigned": "shift.assigned",
    "goal_achieved": "performance.goal_achieved",
    "contact_created": "contact.created", "contact_updated": "contact.updated",
}
SUBSCRIBER_TYPES = ("webhook", "log")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _matches(pattern: str, event_type: str) -> bool:
    """Match an event type against an exact type, a prefix wildcard (lead.*) or *."""
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return event_type == pattern[:-2] or event_type.startswith(pattern[:-1])
    return pattern == event_type


class EventBus:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        from fastapi import HTTPException, status
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage the event bus.")

    @staticmethod
    def catalog() -> dict:
        return {
            "families": EVENT_FAMILIES,
            "event_types": EVENT_TYPES,
            "all_event_types": ALL_EVENT_TYPES,
            "subscriber_types": list(SUBSCRIBER_TYPES),
        }

    # ================= publish =================
    async def publish_from_trigger(self, trigger: str, entity, actor, entity_type: str) -> None:
        """Entry point that replaces the direct workflow dispatch hook. Best-effort:
        never lets a bus problem break the originating action."""
        try:
            event_type = TRIGGER_EVENT_MAP.get(trigger, f"domain.{trigger}")
            await self.publish(event_type, live_entity=entity, actor=actor, entity_type=entity_type,
                               source="trigger", trigger=trigger,
                               entity_id=str(getattr(entity, "id", "")) or None,
                               payload=self._entity_payload(entity))
        except Exception:
            pass

    async def publish(self, event_type: str, *, live_entity=None, actor=None, entity_type: str | None = None,
                      entity_id: str | None = None, payload: dict | None = None, source: str = "custom",
                      trigger: str | None = None, organization_id: uuid.UUID | None = None) -> Event:
        """Publish an event and deliver it to every matching subscriber (built-in
        + configured), each with retry / DLQ / execution-log recording."""
        org_id = organization_id or getattr(actor, "organization_id", None) or getattr(live_entity, "organization_id", None)
        started = time.monotonic()
        payload = self._sanitize(payload)  # never let a non-JSON value poison the session on flush
        ev = Event(organization_id=org_id, event_type=event_type, entity_type=entity_type,
                   entity_id=entity_id, payload=payload, actor_user_id=getattr(actor, "id", None),
                   source=source, status="published", published_at=_now())
        self.db.add(ev)
        await self.db.flush()

        token = _dispatching.set(True)
        delivered = failed = subs = 0
        try:
            # 1) built-in in-process subscribers (receive the live entity)
            if trigger and getattr(actor, "id", None) is not None and live_entity is not None:
                subs += 1
                ok = await self._deliver_workflow_engine(ev, trigger, live_entity, actor, entity_type)
                delivered += 1 if ok else 0
                failed += 0 if ok else 1

            # 2) configured subscribers (webhook / log) matched by pattern
            rows = (await self.db.execute(select(EventSubscription).filter(
                EventSubscription.organization_id == org_id, EventSubscription.is_active == True,
                EventSubscription.is_deleted == False))).scalars().all()
            for sub in rows:
                if not _matches(sub.event_pattern, event_type):
                    continue
                subs += 1
                ok = await self._deliver_subscription(ev, sub, payload or {})
                if ok:
                    delivered += 1
                    sub.delivered_count = (sub.delivered_count or 0) + 1
                else:
                    failed += 1
                    sub.failed_count = (sub.failed_count or 0) + 1
                self.db.add(sub)
        finally:
            _dispatching.reset(token)

        ev.subscriber_count = subs
        ev.delivered_count = delivered
        ev.failed_count = failed
        ev.duration_ms = int((time.monotonic() - started) * 1000)
        self.db.add(ev)
        await self.db.flush()
        return ev

    @staticmethod
    def is_dispatching() -> bool:
        return _dispatching.get()

    # ---------- built-in subscriber: workflow engine ----------
    async def _deliver_workflow_engine(self, ev: Event, trigger: str, entity, actor, entity_type: str) -> bool:
        started = time.monotonic()
        error = None
        try:
            from app.services.workflow_engine_service import WorkflowEngineService
            await WorkflowEngineService(self.db).dispatch(trigger, entity, actor, entity_type)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        self._record_delivery(ev, None, "workflow_engine", 1, error, started, max_attempts=1)
        return error is None

    # ---------- configured subscriber delivery (retry + DLQ) ----------
    async def _deliver_subscription(self, ev: Event, sub: EventSubscription, payload: dict) -> bool:
        started = time.monotonic()
        attempts = 0
        error = None
        max_attempts = max(1, sub.max_attempts or 1)
        for attempts in range(1, max_attempts + 1):
            try:
                await self._invoke_subscriber(sub, ev, payload)
                error = None
                break
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
        self._record_delivery(ev, sub.id, sub.name, attempts, error, started, max_attempts=max_attempts)
        return error is None

    async def _invoke_subscriber(self, sub: EventSubscription, ev: Event, payload: dict):
        if sub.subscriber_type == "log":
            return  # log sink is a no-op success (the EventDelivery row IS the log)
        if sub.subscriber_type == "webhook":
            url = (sub.config or {}).get("url")
            if not url:
                raise ValueError("Webhook subscription has no url configured.")
            import httpx
            body = {"event_type": ev.event_type, "entity_type": ev.entity_type,
                    "entity_id": ev.entity_id, "payload": payload,
                    "published_at": ev.published_at.isoformat() if ev.published_at else None}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=body)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Webhook returned {resp.status_code}")
            return
        raise ValueError(f"Unknown subscriber_type: {sub.subscriber_type}")

    def _record_delivery(self, ev: Event, sub_id, subscriber: str, attempts: int, error: str | None,
                         started: float, max_attempts: int):
        exhausted = error is not None and attempts >= max_attempts
        d = EventDelivery(organization_id=ev.organization_id, event_id=ev.id, subscription_id=sub_id,
                          subscriber=subscriber, event_type=ev.event_type,
                          status=("dead_letter" if exhausted else ("failed" if error else "success")),
                          attempts=attempts, error=error,
                          duration_ms=int((time.monotonic() - started) * 1000),
                          is_dead_letter=exhausted, delivered_at=_now())
        self.db.add(d)

    # ================= custom + manual publish =================
    async def publish_custom(self, actor: User, name: str, payload: dict | None = None,
                             entity_type: str | None = None, entity_id: str | None = None) -> Event:
        self._require_manager(actor)
        event_type = name if name.startswith("custom.") else f"custom.{name}"
        return await self.publish(event_type, actor=actor, entity_type=entity_type, entity_id=entity_id,
                                  payload=payload or {}, source="custom",
                                  organization_id=actor.organization_id)

    # ================= subscriptions CRUD =================
    async def list_subscriptions(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(EventSubscription).filter(
            EventSubscription.organization_id == actor.organization_id, EventSubscription.is_deleted == False
        ).order_by(EventSubscription.created_at.desc()))).scalars().all()
        return [self._sub_dict(r) for r in rows]

    async def create_subscription(self, actor: User, data: dict) -> dict:
        from fastapi import HTTPException, status
        self._require_manager(actor)
        if data.get("subscriber_type") and data["subscriber_type"] not in SUBSCRIBER_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"subscriber_type must be one of {SUBSCRIBER_TYPES}")
        if (data.get("subscriber_type") or "webhook") == "webhook" and not (data.get("config") or {}).get("url"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook subscriptions require config.url")
        sub = EventSubscription(organization_id=actor.organization_id, name=data["name"],
                                event_pattern=data.get("event_pattern") or "*",
                                subscriber_type=data.get("subscriber_type") or "webhook",
                                config=data.get("config"), is_active=bool(data.get("is_active", True)),
                                max_attempts=max(1, min(int(data.get("max_attempts", 3)), 10)), created_by=actor.id)
        self.db.add(sub)
        await self.db.flush()
        return self._sub_dict(sub)

    async def update_subscription(self, actor: User, sub_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        sub = await self._get_sub(actor, sub_id)
        for f in ("name", "event_pattern", "subscriber_type", "config", "is_active", "max_attempts"):
            if f in data and data[f] is not None:
                setattr(sub, f, data[f])
        self.db.add(sub)
        await self.db.flush()
        return self._sub_dict(sub)

    async def delete_subscription(self, actor: User, sub_id: uuid.UUID) -> None:
        self._require_manager(actor)
        sub = await self._get_sub(actor, sub_id)
        sub.is_deleted = True
        self.db.add(sub)
        await self.db.flush()

    async def _get_sub(self, actor: User, sub_id: uuid.UUID) -> EventSubscription:
        from fastapi import HTTPException, status
        sub = (await self.db.execute(select(EventSubscription).filter(
            EventSubscription.id == sub_id, EventSubscription.organization_id == actor.organization_id,
            EventSubscription.is_deleted == False))).scalars().first()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")
        return sub

    # ================= execution logs / DLQ =================
    async def list_events(self, actor: User, event_type: str | None = None, limit: int = 50) -> list[dict]:
        q = select(Event).filter(Event.organization_id == actor.organization_id, Event.is_deleted == False)
        if event_type:
            q = q.filter(Event.event_type == event_type)
        q = q.order_by(Event.published_at.desc()).limit(min(limit, 200))
        return [self._event_dict(e) for e in (await self.db.execute(q)).scalars().all()]

    async def event_deliveries(self, actor: User, event_id: uuid.UUID) -> list[dict]:
        rows = (await self.db.execute(select(EventDelivery).filter(
            EventDelivery.event_id == event_id, EventDelivery.organization_id == actor.organization_id
        ).order_by(EventDelivery.delivered_at.asc()))).scalars().all()
        return [self._delivery_dict(d) for d in rows]

    async def dead_letter_queue(self, actor: User, limit: int = 50) -> list[dict]:
        rows = (await self.db.execute(select(EventDelivery).filter(
            EventDelivery.organization_id == actor.organization_id, EventDelivery.is_dead_letter == True,
            EventDelivery.status == "dead_letter", EventDelivery.is_deleted == False
        ).order_by(EventDelivery.delivered_at.desc()).limit(min(limit, 200)))).scalars().all()
        return [self._delivery_dict(d) for d in rows]

    async def requeue(self, actor: User, delivery_id: uuid.UUID) -> dict:
        """Re-deliver a dead-lettered delivery to its subscriber."""
        from fastapi import HTTPException, status
        self._require_manager(actor)
        d = (await self.db.execute(select(EventDelivery).filter(
            EventDelivery.id == delivery_id, EventDelivery.organization_id == actor.organization_id))).scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found.")
        if not d.is_dead_letter:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery is not in the dead-letter queue.")
        ev = await self.db.get(Event, d.event_id)
        sub = await self.db.get(EventSubscription, d.subscription_id) if d.subscription_id else None
        if ev is None or sub is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Original event/subscription no longer available.")
        ok = await self._deliver_subscription(ev, sub, ev.payload or {})
        # clear the old DLQ entry once requeued
        d.is_dead_letter = False
        d.status = "success" if ok else "failed"
        self.db.add(d)
        await self.db.flush()
        return {"requeued": True, "delivered": ok}

    # ================= monitoring =================
    async def stats(self, actor: User) -> dict:
        org = actor.organization_id
        total = (await self.db.execute(select(func.count(Event.id)).filter(
            Event.organization_id == org, Event.is_deleted == False))).scalar() or 0
        deliveries = (await self.db.execute(select(func.count(EventDelivery.id)).filter(
            EventDelivery.organization_id == org, EventDelivery.is_deleted == False))).scalar() or 0
        failed = (await self.db.execute(select(func.count(EventDelivery.id)).filter(
            EventDelivery.organization_id == org, EventDelivery.is_deleted == False,
            EventDelivery.status != "success"))).scalar() or 0
        dlq = (await self.db.execute(select(func.count(EventDelivery.id)).filter(
            EventDelivery.organization_id == org, EventDelivery.is_deleted == False,
            EventDelivery.is_dead_letter == True, EventDelivery.status == "dead_letter"))).scalar() or 0
        avg_ms = (await self.db.execute(select(func.avg(Event.duration_ms)).filter(
            Event.organization_id == org, Event.is_deleted == False))).scalar()
        by_type = (await self.db.execute(select(Event.event_type, func.count(Event.id)).filter(
            Event.organization_id == org, Event.is_deleted == False).group_by(Event.event_type))).all()
        return {"total_events": total, "deliveries": deliveries, "failed_deliveries": failed,
                "success_rate": round((deliveries - failed) / deliveries * 100, 1) if deliveries else 100.0,
                "dead_letter": dlq, "avg_publish_ms": round(float(avg_ms), 1) if avg_ms else 0.0,
                "by_type": {k: v for k, v in by_type}}

    async def dashboard(self, actor: User) -> dict:
        st = await self.stats(actor)
        active_subs = (await self.db.execute(select(func.count(EventSubscription.id)).filter(
            EventSubscription.organization_id == actor.organization_id, EventSubscription.is_deleted == False,
            EventSubscription.is_active == True))).scalar() or 0
        recent = await self.list_events(actor, limit=5)
        return {"total_events": st["total_events"], "success_rate": st["success_rate"],
                "dead_letter": st["dead_letter"], "subscriptions": active_subs, "recent": recent}

    # ---------- helpers ----------
    @classmethod
    def _sanitize(cls, payload):
        """Recursively coerce a payload into a JSON-serialisable structure."""
        if payload is None:
            return None
        if isinstance(payload, dict):
            return {str(k): cls._sanitize(v) for k, v in payload.items()}
        if isinstance(payload, (list, tuple)):
            return [cls._sanitize(v) for v in payload]
        return cls._json_safe(payload)

    @staticmethod
    def _json_safe(v):
        """Coerce a value into something json.dumps can handle (the payload is
        persisted to a JSON column — Decimal/datetime/UUID would otherwise raise
        on flush and poison the session)."""
        from decimal import Decimal
        from datetime import datetime, date
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        return str(v)

    @classmethod
    def _entity_payload(cls, entity) -> dict:
        """A small, JSON-safe snapshot of the entity for webhook subscribers."""
        if entity is None:
            return {}
        return {k: cls._json_safe(getattr(entity, k))
                for k in ("id", "status", "priority", "title", "name", "value", "amount", "email", "phone")
                if hasattr(entity, k)}

    def _event_dict(self, e: Event) -> dict:
        return {"id": str(e.id), "event_type": e.event_type, "entity_type": e.entity_type,
                "entity_id": e.entity_id, "source": e.source, "status": e.status,
                "subscriber_count": e.subscriber_count, "delivered_count": e.delivered_count,
                "failed_count": e.failed_count, "duration_ms": e.duration_ms,
                "published_at": e.published_at.isoformat() if e.published_at else None}

    def _sub_dict(self, s: EventSubscription) -> dict:
        return {"id": str(s.id), "name": s.name, "event_pattern": s.event_pattern,
                "subscriber_type": s.subscriber_type, "config": s.config, "is_active": s.is_active,
                "max_attempts": s.max_attempts, "delivered_count": s.delivered_count,
                "failed_count": s.failed_count,
                "created_at": s.created_at.isoformat() if s.created_at else None}

    def _delivery_dict(self, d: EventDelivery) -> dict:
        return {"id": str(d.id), "event_id": str(d.event_id),
                "subscription_id": str(d.subscription_id) if d.subscription_id else None,
                "subscriber": d.subscriber, "event_type": d.event_type, "status": d.status,
                "attempts": d.attempts, "error": d.error, "duration_ms": d.duration_ms,
                "is_dead_letter": d.is_dead_letter,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None}

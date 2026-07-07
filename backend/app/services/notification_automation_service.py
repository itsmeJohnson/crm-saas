"""Notification Automation service.

The rule-driven orchestration layer on top of the existing Notification Center.
Notification rules subscribe to the Event Bus, are gated by the Rule Engine,
resolve recipients, render templates, and deliver over multiple channels —
immediately or batched into a digest — with per-channel delivery tracking and
retry via the Background Queue. The existing direct notification calls (workflow
action, reminders, escalation, approval) are untouched; rules add automated
notifications on top.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.notification import Notification
from app.models.notification_template import NotificationTemplate
from app.models.notification_automation import (
    NotificationRule, NotificationDelivery, NotificationDigestItem,
)
from app.services.notification_service import NotificationService
from app.services import rule_evaluator as ev

RECIPIENT_TYPES = ("owner", "manager", "creator", "role", "user")
CHANNELS = ("in_app", "email", "sms", "whatsapp", "push")
RETRYABLE_CHANNELS = ("email", "sms", "whatsapp")
_CHANNEL_TO_JOB = {"email": "send_email", "sms": "send_sms", "whatsapp": "send_whatsapp"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _render(text: str | None, ctx: dict) -> str:
    """Substitute {{var}} tokens from the context (missing → blank)."""
    if not text:
        return ""
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", lambda m: str(ctx.get(m.group(1), "")), text)


class NotificationAutomationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage notification automation.")

    @staticmethod
    def catalog() -> dict:
        from app.services.event_bus import ALL_EVENT_TYPES
        return {"trigger_events": ["*"] + ALL_EVENT_TYPES, "recipient_types": list(RECIPIENT_TYPES),
                "channels": list(CHANNELS), "priorities": ["low", "normal", "high"]}

    # ================= rule CRUD =================
    def _validate(self, data: dict):
        for r in (data.get("recipients") or []):
            if r.get("type") not in RECIPIENT_TYPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"recipient type must be one of {RECIPIENT_TYPES}")
        for c in (data.get("channels") or []):
            if c not in CHANNELS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"channel must be one of {CHANNELS}")

    async def _get(self, actor: User, rule_id: uuid.UUID) -> NotificationRule:
        r = (await self.db.execute(select(NotificationRule).filter(
            NotificationRule.id == rule_id, NotificationRule.organization_id == actor.organization_id,
            NotificationRule.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification rule not found.")
        return r

    async def list_rules(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(NotificationRule).filter(
            NotificationRule.organization_id == actor.organization_id, NotificationRule.is_deleted == False
        ).order_by(NotificationRule.created_at.desc()))).scalars().all()
        return [self._rule_dict(r) for r in rows]

    async def create_rule(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        r = NotificationRule(organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
                             trigger_event=data["trigger_event"], entity_type=data.get("entity_type"),
                             conditions=data.get("conditions"), recipients=data.get("recipients") or [],
                             channels=data.get("channels") or ["in_app"], template_key=data.get("template_key"),
                             title=data.get("title"), body=data.get("body"), category=data.get("category") or "system",
                             priority=data.get("priority") or "normal", digest=bool(data.get("digest", False)),
                             is_active=bool(data.get("is_active", True)), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        return self._rule_dict(r)

    async def update_rule(self, actor: User, rule_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        r = await self._get(actor, rule_id)
        for f in ("name", "description", "trigger_event", "entity_type", "conditions", "recipients",
                  "channels", "template_key", "title", "body", "category", "priority", "digest", "is_active"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        self.db.add(r)
        await self.db.flush()
        return self._rule_dict(r)

    async def delete_rule(self, actor: User, rule_id: uuid.UUID) -> None:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        r.is_deleted = True
        self.db.add(r)
        await self.db.flush()

    async def set_enabled(self, actor: User, rule_id: uuid.UUID, enabled: bool) -> dict:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        r.is_active = enabled
        self.db.add(r)
        await self.db.flush()
        return self._rule_dict(r)

    # ================= event handling (Event Bus subscriber) =================
    async def handle_event(self, event_type: str, live_entity, actor, payload: dict | None,
                           org_id: uuid.UUID) -> int:
        """Fire every active rule matching this event. Returns notifications sent.
        Best-effort — never raises into the publish path."""
        if event_type == "notification.created":  # never let rules react to their own output
            return 0
        rules = (await self.db.execute(select(NotificationRule).filter(
            NotificationRule.organization_id == org_id, NotificationRule.is_active == True,
            NotificationRule.is_deleted == False))).scalars().all()
        total = 0
        for rule in rules:
            if rule.trigger_event not in ("*", event_type):
                continue
            facts = self._facts(live_entity, payload)
            if rule.conditions and not ev.evaluate(rule.conditions, facts, {"now": _now()}):
                continue
            rule.run_count = (rule.run_count or 0) + 1
            targets = await self._resolve_recipients(rule, live_entity, org_id)
            ctx = self._context(live_entity, payload, actor)
            title = _render(rule.title, ctx) or await self._template_title(rule, ctx) or rule.name
            body = _render(rule.body, ctx) or await self._template_body(rule, ctx) or ""
            link = f"/{(rule.entity_type or 'notifications')}s"
            for uid in targets:
                if rule.digest:
                    self.db.add(NotificationDigestItem(organization_id=org_id, user_id=uid, rule_id=rule.id,
                                                       category=rule.category, title=title, body=body, link_url=link))
                else:
                    await self._deliver(rule, uid, title, body, link, org_id, actor)
                rule.notif_count = (rule.notif_count or 0) + 1
                total += 1
            self.db.add(rule)
        await self.db.flush()
        return total

    async def _resolve_recipients(self, rule: NotificationRule, entity, org_id) -> set[uuid.UUID]:
        out: set[uuid.UUID] = set()
        owner = getattr(entity, "assigned_user_id", None) if entity is not None else None
        for spec in (rule.recipients or []):
            t, val = spec.get("type"), spec.get("value")
            if t == "owner" and owner:
                out.add(owner)
            elif t == "creator" and entity is not None and getattr(entity, "created_by", None):
                out.add(entity.created_by)
            elif t == "manager" and owner:
                mgr = (await self.db.execute(select(User.reporting_to_id).filter(User.id == owner))).scalar()
                if mgr:
                    out.add(mgr)
            elif t == "user" and val:
                try:
                    out.add(uuid.UUID(str(val)))
                except (ValueError, TypeError):
                    pass
            elif t == "role" and val:
                ids = (await self.db.execute(select(User.id).filter(
                    User.organization_id == org_id, User.role == val, User.is_active == True,
                    User.is_deleted == False))).scalars().all()
                out.update(ids)
        return out

    async def _deliver(self, rule: NotificationRule, user_id: uuid.UUID, title: str, body: str,
                       link: str, org_id: uuid.UUID, actor) -> None:
        """Create the in-app notification and a per-channel delivery record; retry
        failed messaging channels via the Background Queue."""
        prefs = await self.notifier._effective_prefs(user_id, rule.category)
        notif = None
        if "in_app" in rule.channels and prefs.get("in_app", True):
            notif = await self.notifier.create_notification(
                organization_id=org_id, user_id=user_id, category=rule.category, title=title, body=body,
                link_url=link, priority=rule.priority, channels_sent=list(rule.channels))
            self._track(org_id, notif, rule, user_id, "in_app", "sent", title)

        user = await self.db.get(User, user_id)
        for channel in rule.channels:
            if channel == "in_app":
                continue
            if not prefs.get(channel, False):
                continue
            ok = False
            try:
                if channel == "email" and user and user.email:
                    ok = await self.notifier._send_email(user, title, body)
                elif channel == "sms" and user and getattr(user, "phone", None):
                    ok = await self.notifier._send_sms(user, title, body)
                elif channel == "whatsapp" and user and getattr(user, "phone", None):
                    ok = await self.notifier._send_whatsapp(user, title, body)
                elif channel == "push":
                    ok = await self.notifier._send_push(org_id, user_id, title, body, link)
            except Exception:
                ok = False
            if ok:
                self._track(org_id, notif, rule, user_id, channel, "sent", title)
            elif channel in RETRYABLE_CHANNELS:
                job_id = await self._enqueue_retry(channel, user, title, body, org_id, actor)
                self._track(org_id, notif, rule, user_id, channel, "retrying", title, error="initial send failed", job_id=job_id)
            else:
                self._track(org_id, notif, rule, user_id, channel, "failed", title, error="send failed")

    async def _enqueue_retry(self, channel: str, user, title: str, body: str, org_id, actor) -> uuid.UUID | None:
        try:
            from app.services.queue_service import QueueService
            payload = {"subject": title, "body": body}
            if channel == "email":
                payload["to"] = getattr(user, "email", None)
            else:
                payload["to_number"] = getattr(user, "phone", None)
            job = await QueueService(self.db).enqueue(
                organization_id=org_id, job_type=_CHANNEL_TO_JOB[channel], payload=payload,
                created_by=getattr(actor, "id", None), max_attempts=3)
            return job.id
        except Exception:
            return None

    def _track(self, org_id, notif, rule, user_id, channel, status_val, title, error=None, job_id=None):
        self.db.add(NotificationDelivery(
            organization_id=org_id, notification_id=(notif.id if notif else None), rule_id=rule.id,
            user_id=user_id, channel=channel, status=status_val, attempts=1, error=error,
            queue_job_id=job_id, title=title, sent_at=_now() if status_val == "sent" else None))

    @staticmethod
    def _facts(entity, payload) -> dict:
        facts = dict(payload or {})
        if entity is not None:
            for k in ("status", "source", "priority", "value", "score", "city", "company_name",
                      "amount", "request_type", "day_count"):
                if hasattr(entity, k):
                    v = getattr(entity, k)
                    facts.setdefault(k, str(v) if isinstance(v, uuid.UUID) else v)
        return facts

    @staticmethod
    def _context(entity, payload, actor) -> dict:
        ctx = {k: ("" if v is None else str(v)) for k, v in (payload or {}).items()}
        if entity is not None:
            for k in ("title", "name", "status", "priority", "value", "amount", "first_name", "last_name"):
                if hasattr(entity, k) and getattr(entity, k) is not None:
                    ctx.setdefault(k, str(getattr(entity, k)))
        if actor is not None:
            ctx.setdefault("actor", f"{getattr(actor, 'first_name', '') or ''} {getattr(actor, 'last_name', '') or ''}".strip())
        return ctx

    async def _template_title(self, rule: NotificationRule, ctx: dict) -> str | None:
        tpl = await self._template(rule.organization_id, rule.template_key)
        return _render(tpl.subject, ctx) if tpl and tpl.subject else None

    async def _template_body(self, rule: NotificationRule, ctx: dict) -> str | None:
        tpl = await self._template(rule.organization_id, rule.template_key)
        return _render(tpl.body, ctx) if tpl else None

    async def _template(self, org_id, key) -> NotificationTemplate | None:
        if not key:
            return None
        return (await self.db.execute(select(NotificationTemplate).filter(
            NotificationTemplate.template_key == self._tkey(org_id, key)))).scalars().first()

    # ================= digests (Scheduler-driven) =================
    async def flush_digests(self, org_id: uuid.UUID) -> int:
        """Compose one summary notification per user from their pending digest
        items, then mark the items sent. Returns digests sent."""
        items = (await self.db.execute(select(NotificationDigestItem).filter(
            NotificationDigestItem.organization_id == org_id, NotificationDigestItem.is_sent == False,
            NotificationDigestItem.is_deleted == False).order_by(NotificationDigestItem.created_at.asc()))).scalars().all()
        by_user: dict[uuid.UUID, list[NotificationDigestItem]] = {}
        for it in items:
            by_user.setdefault(it.user_id, []).append(it)
        sent = 0
        for uid, group in by_user.items():
            lines = "\n".join(f"• {g.title}" for g in group[:20])
            more = f"\n…and {len(group) - 20} more" if len(group) > 20 else ""
            await self.notifier.create_notification(
                organization_id=org_id, user_id=uid, category="digest",
                title=f"You have {len(group)} update(s)", body=lines + more, link_url="/notifications")
            for g in group:
                g.is_sent = True
                self.db.add(g)
            sent += 1
        await self.db.flush()
        return sent

    async def run_digest_now(self, actor: User) -> dict:
        self._require_manager(actor)
        return {"digests_sent": await self.flush_digests(actor.organization_id)}

    # ================= delivery tracking / retry =================
    async def deliveries(self, actor: User, status_filter: str | None = None, channel: str | None = None,
                         rule_id: uuid.UUID | None = None, limit: int = 50) -> list[dict]:
        q = select(NotificationDelivery).filter(NotificationDelivery.organization_id == actor.organization_id,
                                                NotificationDelivery.is_deleted == False)
        if status_filter:
            q = q.filter(NotificationDelivery.status == status_filter)
        if channel:
            q = q.filter(NotificationDelivery.channel == channel)
        if rule_id:
            q = q.filter(NotificationDelivery.rule_id == rule_id)
        q = q.order_by(NotificationDelivery.created_at.desc()).limit(min(limit, 200))
        return [self._delivery_dict(d) for d in (await self.db.execute(q)).scalars().all()]

    async def retry_delivery(self, actor: User, delivery_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        d = (await self.db.execute(select(NotificationDelivery).filter(
            NotificationDelivery.id == delivery_id, NotificationDelivery.organization_id == actor.organization_id))).scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found.")
        if d.status not in ("failed", "retrying"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed/retrying deliveries can be retried.")
        user = await self.db.get(User, d.user_id)
        ok = False
        try:
            if d.channel == "email" and user and user.email:
                ok = await self.notifier._send_email(user, d.title or "Notification", "")
            elif d.channel == "sms" and user and getattr(user, "phone", None):
                ok = await self.notifier._send_sms(user, d.title or "Notification", "")
            elif d.channel == "whatsapp" and user and getattr(user, "phone", None):
                ok = await self.notifier._send_whatsapp(user, d.title or "Notification", "")
        except Exception:
            ok = False
        d.attempts = (d.attempts or 1) + 1
        d.status = "sent" if ok else "failed"
        d.sent_at = _now() if ok else d.sent_at
        d.error = None if ok else (d.error or "retry failed")
        self.db.add(d)
        await self.db.flush()
        return self._delivery_dict(d)

    # ================= templates (activate the unused NotificationTemplate) =================
    @staticmethod
    def _tkey(org_id, key: str) -> str:
        """Namespace template keys by org so tenants never collide (the model's
        template_key is globally unique and shared with platform seeds)."""
        return f"org:{org_id}:{key}"

    async def list_templates(self, actor: User) -> list[dict]:
        prefix = f"org:{actor.organization_id}:"
        rows = (await self.db.execute(select(NotificationTemplate).filter(
            NotificationTemplate.template_key.like(prefix + "%"),
            NotificationTemplate.is_deleted == False))).scalars().all()
        return [self._tpl_dict(t) for t in rows]

    async def create_template(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        full = self._tkey(actor.organization_id, data["template_key"])
        exists = (await self.db.execute(select(NotificationTemplate).filter(
            NotificationTemplate.template_key == full))).scalars().first()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A template with that key already exists.")
        t = NotificationTemplate(template_key=full, template_name=data["template_name"],
                                 channel=data.get("channel") or "email", subject=data.get("subject"),
                                 body=data.get("body") or "", variables=data.get("variables"),
                                 category=data.get("category") or "system", description=data.get("description"))
        self.db.add(t)
        await self.db.flush()
        return self._tpl_dict(t)

    async def update_template(self, actor: User, template_key: str, data: dict) -> dict:
        self._require_manager(actor)
        t = await self._template(actor.organization_id, template_key)
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
        for f in ("template_name", "channel", "subject", "body", "variables", "category", "description", "is_active"):
            if f in data and data[f] is not None:
                setattr(t, f, data[f])
        self.db.add(t)
        await self.db.flush()
        return self._tpl_dict(t)

    async def delete_template(self, actor: User, template_key: str) -> None:
        self._require_manager(actor)
        t = await self._template(actor.organization_id, template_key)
        if t:
            t.is_deleted = True
            self.db.add(t)
            await self.db.flush()

    # ================= reports / dashboard =================
    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        rules = (await self.db.execute(select(func.count(NotificationRule.id)).filter(
            NotificationRule.organization_id == org, NotificationRule.is_deleted == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(NotificationRule.id)).filter(
            NotificationRule.organization_id == org, NotificationRule.is_deleted == False,
            NotificationRule.is_active == True))).scalar() or 0
        by_channel = dict((c, n) for c, n in (await self.db.execute(
            select(NotificationDelivery.channel, func.count(NotificationDelivery.id)).filter(
                NotificationDelivery.organization_id == org, NotificationDelivery.is_deleted == False
            ).group_by(NotificationDelivery.channel))).all())
        by_status = dict((s, n) for s, n in (await self.db.execute(
            select(NotificationDelivery.status, func.count(NotificationDelivery.id)).filter(
                NotificationDelivery.organization_id == org, NotificationDelivery.is_deleted == False
            ).group_by(NotificationDelivery.status))).all())
        total = sum(by_status.values())
        sent = by_status.get("sent", 0)
        pending_digest = (await self.db.execute(select(func.count(NotificationDigestItem.id)).filter(
            NotificationDigestItem.organization_id == org, NotificationDigestItem.is_sent == False,
            NotificationDigestItem.is_deleted == False))).scalar() or 0
        return {"rules": rules, "active_rules": active, "deliveries": total,
                "delivery_rate": round(sent / total * 100, 1) if total else 100.0,
                "by_channel": by_channel, "by_status": by_status, "pending_digest": pending_digest}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        recent = await self.deliveries(actor, limit=5)
        return {"rules": rep["rules"], "active_rules": rep["active_rules"], "deliveries": rep["deliveries"],
                "delivery_rate": rep["delivery_rate"], "pending_digest": rep["pending_digest"],
                "failed": rep["by_status"].get("failed", 0) + rep["by_status"].get("retrying", 0),
                "recent": recent}

    # ---------- serialize ----------
    def _rule_dict(self, r: NotificationRule) -> dict:
        return {"id": str(r.id), "name": r.name, "description": r.description, "trigger_event": r.trigger_event,
                "entity_type": r.entity_type, "conditions": r.conditions, "recipients": r.recipients,
                "channels": r.channels, "template_key": r.template_key, "title": r.title, "body": r.body,
                "category": r.category, "priority": r.priority, "digest": r.digest, "is_active": r.is_active,
                "run_count": r.run_count, "notif_count": r.notif_count,
                "created_at": r.created_at.isoformat() if r.created_at else None}

    def _delivery_dict(self, d: NotificationDelivery) -> dict:
        return {"id": str(d.id), "rule_id": str(d.rule_id) if d.rule_id else None, "user_id": str(d.user_id),
                "channel": d.channel, "status": d.status, "attempts": d.attempts, "error": d.error,
                "title": d.title, "queue_job_id": str(d.queue_job_id) if d.queue_job_id else None,
                "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None}

    def _tpl_dict(self, t: NotificationTemplate) -> dict:
        return {"template_key": t.template_key.split(":", 2)[-1], "template_name": t.template_name,
                "channel": t.channel, "subject": t.subject, "body": t.body, "variables": t.variables,
                "category": t.category, "description": t.description, "is_active": t.is_active}

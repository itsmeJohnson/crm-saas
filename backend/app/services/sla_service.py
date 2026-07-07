"""SLA Management service.

The first-class SLA layer: policies with priority tiers and response/resolution
targets, a per-entity SLA clock (SLATracker) that is business-hours and holiday
aware and supports pause/resume, breach detection that emits an `sla.breached`
event (so Workflows and Notification rules react), escalation, a dashboard and
compliance reports.

Builds on the Automation Engine's SLAPolicy/SLABreach (extended, not replaced);
that engine's lightweight `run_sla_scan` keeps working and shares SLABreach via
the same dedup guard.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.automation import SLAPolicy, SLABreach
from app.models.sla import SLATracker, SLAPause
from app.models.calendar_event import WorkingHoursConfig, Holiday
from app.services import business_time as bt
from app.services import rule_evaluator as ev

SLA_ENTITY_TYPES = ("lead",)
BREACH_ACTIONS = ("notify_owner", "notify_manager", "escalate")
TRACKER_STATUSES = ("running", "paused", "met", "breached", "cancelled")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


class SLAService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage SLA policies.")

    @staticmethod
    def catalog() -> dict:
        return {"entity_types": list(SLA_ENTITY_TYPES), "metrics": ["first_response", "resolution"],
                "breach_actions": list(BREACH_ACTIONS), "tracker_statuses": list(TRACKER_STATUSES)}

    # ================= policy CRUD (rich, over sla_policies) =================
    def _validate(self, data: dict):
        if data.get("on_breach") and data["on_breach"] not in BREACH_ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"on_breach must be one of {BREACH_ACTIONS}")
        for tier in (data.get("priorities") or []):
            if not tier.get("level"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each priority tier needs a 'level'.")

    async def _get(self, actor: User, policy_id: uuid.UUID) -> SLAPolicy:
        p = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.id == policy_id, SLAPolicy.organization_id == actor.organization_id,
            SLAPolicy.is_deleted == False))).scalars().first()
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA policy not found.")
        return p

    async def list_policies(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.organization_id == actor.organization_id, SLAPolicy.is_deleted == False
        ).order_by(SLAPolicy.created_at.desc()))).scalars().all()
        return [self._policy_dict(p) for p in rows]

    async def create_policy(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        p = SLAPolicy(organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
                      entity_type=data.get("entity_type") or "lead", metric=data.get("metric") or "first_response",
                      threshold_hours=float(data.get("response_hours") or data.get("threshold_hours") or 24.0),
                      conditions=data.get("conditions"), on_breach=data.get("on_breach") or "notify_manager",
                      is_active=bool(data.get("is_active", True)), created_by=actor.id,
                      priority_field=data.get("priority_field") or "priority", priorities=data.get("priorities"),
                      response_hours=data.get("response_hours"), resolution_hours=data.get("resolution_hours"),
                      business_hours_only=bool(data.get("business_hours_only", False)),
                      skip_holidays=bool(data.get("skip_holidays", False)),
                      escalate_after_hours=data.get("escalate_after_hours"), escalate_to_role=data.get("escalate_to_role"))
        self.db.add(p)
        await self.db.flush()
        return self._policy_dict(p)

    async def update_policy(self, actor: User, policy_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        p = await self._get(actor, policy_id)
        for f in ("name", "description", "entity_type", "metric", "conditions", "on_breach", "is_active",
                  "priority_field", "priorities", "response_hours", "resolution_hours",
                  "business_hours_only", "skip_holidays", "escalate_after_hours", "escalate_to_role"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        if data.get("response_hours") is not None:
            p.threshold_hours = float(data["response_hours"])
        self.db.add(p)
        await self.db.flush()
        return self._policy_dict(p)

    async def delete_policy(self, actor: User, policy_id: uuid.UUID) -> None:
        self._require_manager(actor)
        p = await self._get(actor, policy_id)
        p.is_deleted = True
        self.db.add(p)
        await self.db.flush()

    async def set_enabled(self, actor: User, policy_id: uuid.UUID, enabled: bool) -> dict:
        self._require_manager(actor)
        p = await self._get(actor, policy_id)
        p.is_active = enabled
        self.db.add(p)
        await self.db.flush()
        return self._policy_dict(p)

    # ================= business-hours-aware due computation =================
    async def _working_context(self, org_id: uuid.UUID):
        cfg = (await self.db.execute(select(WorkingHoursConfig).filter(
            WorkingHoursConfig.organization_id == org_id))).scalars().first()
        tzname = cfg.timezone if cfg else "UTC"
        days = cfg.days if cfg else None
        hols = [(h.holiday_date, h.recurring_annual) for h in (await self.db.execute(select(Holiday).filter(
            Holiday.organization_id == org_id, Holiday.is_deleted == False))).scalars().all()]
        return tzname, days, hols

    def _due(self, start_utc: datetime, hours: float, business_only: bool, skip_holidays: bool,
             tzname: str, days, hols) -> datetime:
        if not hours or hours <= 0:
            return start_utc
        if not business_only:
            return start_utc + timedelta(hours=hours)
        tz = _tz(tzname)
        local = start_utc.astimezone(tz).replace(tzinfo=None)
        due_local = bt.add_business_hours(local, hours, days, hols if skip_holidays else _WEEKENDS_ONLY(hols))
        return due_local.replace(tzinfo=tz).astimezone(timezone.utc)

    # ================= tracker lifecycle =================
    async def start_tracking(self, entity, entity_type: str, org_id: uuid.UUID) -> int:
        """Open an SLA clock for every matching active policy. Idempotent per
        (policy, entity). Returns trackers opened."""
        policies = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.organization_id == org_id, SLAPolicy.entity_type == entity_type,
            SLAPolicy.is_active == True, SLAPolicy.is_deleted == False))).scalars().all()
        if not policies:
            return 0
        tzname, days, hols = await self._working_context(org_id)
        now = _now()
        opened = 0
        for policy in policies:
            if policy.conditions and not ev.evaluate(policy.conditions, self._facts(entity), {"now": now}):
                continue
            exists = (await self.db.execute(select(SLATracker.id).filter(
                SLATracker.policy_id == policy.id, SLATracker.entity_id == getattr(entity, "id"),
                SLATracker.is_deleted == False))).scalars().first()
            if exists:
                continue
            resp_h, reso_h, level = self._thresholds(policy, entity)
            t = SLATracker(organization_id=org_id, policy_id=policy.id, entity_type=entity_type,
                           entity_id=getattr(entity, "id"), priority_level=level, status="running", started_at=now,
                           response_hours=resp_h, resolution_hours=reso_h)
            if resp_h:
                t.response_due_at = self._due(now, resp_h, policy.business_hours_only, policy.skip_holidays, tzname, days, hols)
            if reso_h:
                t.resolution_due_at = self._due(now, reso_h, policy.business_hours_only, policy.skip_holidays, tzname, days, hols)
            self.db.add(t)
            opened += 1
        await self.db.flush()
        return opened

    def _thresholds(self, policy: SLAPolicy, entity) -> tuple[float | None, float | None, str | None]:
        """Resolve response/resolution hours, honouring priority tiers."""
        resp = policy.response_hours if policy.response_hours is not None else policy.threshold_hours
        reso = policy.resolution_hours
        level = None
        if policy.priorities:
            pval = getattr(entity, policy.priority_field or "priority", None)
            if pval is not None:
                level = str(pval)
                for tier in policy.priorities:
                    if str(tier.get("level")).lower() == level.lower():
                        if tier.get("response_hours") is not None:
                            resp = float(tier["response_hours"])
                        if tier.get("resolution_hours") is not None:
                            reso = float(tier["resolution_hours"])
                        break
        return resp, reso, level

    async def record_response(self, entity_type: str, entity_id: uuid.UUID, org_id: uuid.UUID) -> int:
        rows = (await self.db.execute(select(SLATracker).filter(
            SLATracker.organization_id == org_id, SLATracker.entity_type == entity_type,
            SLATracker.entity_id == entity_id, SLATracker.first_response_at.is_(None),
            SLATracker.status.in_(["running", "paused"]), SLATracker.is_deleted == False))).scalars().all()
        now = _now()
        for t in rows:
            t.first_response_at = now
            due = _aware(t.response_due_at)
            if due and now > due:
                t.response_breached = True
            self.db.add(t)
        await self.db.flush()
        return len(rows)

    async def record_resolution(self, entity_type: str, entity_id: uuid.UUID, org_id: uuid.UUID) -> int:
        rows = (await self.db.execute(select(SLATracker).filter(
            SLATracker.organization_id == org_id, SLATracker.entity_type == entity_type,
            SLATracker.entity_id == entity_id, SLATracker.resolved_at.is_(None),
            SLATracker.status.in_(["running", "paused"]), SLATracker.is_deleted == False))).scalars().all()
        now = _now()
        for t in rows:
            t.resolved_at = now
            due = _aware(t.resolution_due_at)
            if due and now > due:
                t.resolution_breached = True
                t.status = "breached"
            else:
                t.status = "met"
            self.db.add(t)
        await self.db.flush()
        return len(rows)

    # ================= pause / resume =================
    async def _get_tracker(self, actor: User, tracker_id: uuid.UUID) -> SLATracker:
        t = (await self.db.execute(select(SLATracker).filter(
            SLATracker.id == tracker_id, SLATracker.organization_id == actor.organization_id,
            SLATracker.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA tracker not found.")
        return t

    async def pause(self, actor: User, tracker_id: uuid.UUID, reason: str | None = None) -> dict:
        self._require_manager(actor)
        t = await self._get_tracker(actor, tracker_id)
        if t.status != "running":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only a running SLA can be paused (status={t.status}).")
        now = _now()
        t.status = "paused"
        t.paused_at = now
        self.db.add(t)
        self.db.add(SLAPause(organization_id=t.organization_id, tracker_id=t.id, reason=reason,
                             paused_at=now, paused_by=actor.id))
        await self.db.flush()
        return self._tracker_dict(t)

    async def resume(self, actor: User, tracker_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        t = await self._get_tracker(actor, tracker_id)
        if t.status != "paused":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only a paused SLA can be resumed (status={t.status}).")
        now = _now()
        delta = int((now - _aware(t.paused_at)).total_seconds()) if t.paused_at else 0
        t.paused_seconds = (t.paused_seconds or 0) + delta
        # extend deadlines by the paused duration so the clock effectively stopped
        if t.response_due_at and not t.first_response_at:
            t.response_due_at = _aware(t.response_due_at) + timedelta(seconds=delta)
        if t.resolution_due_at and not t.resolved_at:
            t.resolution_due_at = _aware(t.resolution_due_at) + timedelta(seconds=delta)
        t.paused_at = None
        t.status = "running"
        self.db.add(t)
        row = (await self.db.execute(select(SLAPause).filter(
            SLAPause.tracker_id == t.id, SLAPause.resumed_at.is_(None)).order_by(SLAPause.paused_at.desc()))).scalars().first()
        if row:
            row.resumed_at = now
            self.db.add(row)
        await self.db.flush()
        return self._tracker_dict(t)

    # ================= breach scan =================
    async def scan(self, org_id: uuid.UUID) -> int:
        """Flag response/resolution breaches on running trackers, record an
        SLABreach, emit sla.breached (→ Workflows + Notification rules), escalate."""
        now = _now()
        trackers = (await self.db.execute(select(SLATracker).filter(
            SLATracker.organization_id == org_id, SLATracker.status == "running",
            SLATracker.is_deleted == False))).scalars().all()
        breaches = 0
        for t in trackers:
            policy = await self.db.get(SLAPolicy, t.policy_id)
            if policy is None:
                continue
            # response breach
            rdue = _aware(t.response_due_at)
            if (not t.response_breached and t.first_response_at is None and rdue and now > rdue):
                t.response_breached = True
                if t.status != "breached":
                    t.breach_type = "response"
                    t.breached_at = now
                await self._on_breach(t, policy, "first_response", now)
                breaches += 1
            # resolution breach
            xdue = _aware(t.resolution_due_at)
            if (not t.resolution_breached and t.resolved_at is None and xdue and now > xdue):
                t.resolution_breached = True
                t.breach_type = "resolution"
                t.breached_at = now
                t.status = "breached"
                await self._on_breach(t, policy, "resolution", now)
                breaches += 1
            self.db.add(t)
        await self.db.flush()
        return breaches

    async def _on_breach(self, tracker: SLATracker, policy: SLAPolicy, metric: str, now: datetime):
        org_id = tracker.organization_id
        # dedup-compatible SLABreach row (shared with the automation engine)
        exists = (await self.db.execute(select(SLABreach.id).filter(
            SLABreach.policy_id == policy.id, SLABreach.entity_id == tracker.entity_id,
            SLABreach.metric == metric, SLABreach.resolved == False, SLABreach.is_deleted == False))).scalars().first()
        elapsed = round((now - _aware(tracker.started_at)).total_seconds() / 3600, 2)
        if not exists:
            self.db.add(SLABreach(organization_id=org_id, policy_id=policy.id, entity_type=tracker.entity_type,
                                  entity_id=tracker.entity_id, metric=metric, hours_elapsed=elapsed,
                                  breached_at=now, notified=True))
            policy.breach_count = (policy.breach_count or 0) + 1
            self.db.add(policy)
        # load the entity + an actor (owner/creator) so Workflows can react too
        entity, actor = await self._load_entity_actor(tracker)
        # escalation: notify manager / escalate-to-role directly
        await self._escalate(tracker, policy, metric, entity, org_id)
        # emit the domain event → Event Bus → Workflows + Notification rules
        try:
            from app.services.event_bus import EventBus
            await EventBus(self.db).publish(
                "sla.breached", live_entity=entity, actor=actor, entity_type=tracker.entity_type,
                entity_id=str(tracker.entity_id), source="system", trigger="sla_breached",
                organization_id=org_id,
                payload={"policy": policy.name, "metric": metric, "hours_elapsed": elapsed,
                         "priority": tracker.priority_level})
        except Exception:
            pass

    async def _escalate(self, tracker: SLATracker, policy: SLAPolicy, metric: str, entity, org_id):
        from app.services.notification_service import NotificationService
        targets: set[uuid.UUID] = set()
        owner = getattr(entity, "assigned_user_id", None) if entity is not None else None
        if policy.on_breach == "notify_owner" and owner:
            targets.add(owner)
        elif policy.on_breach in ("notify_manager", "escalate") and owner:
            mgr = (await self.db.execute(select(User.reporting_to_id).filter(User.id == owner))).scalar()
            if mgr:
                targets.add(mgr)
            if policy.on_breach == "escalate":
                targets.add(owner)
        if policy.escalate_to_role:
            ids = (await self.db.execute(select(User.id).filter(
                User.organization_id == org_id, User.role == policy.escalate_to_role,
                User.is_active == True, User.is_deleted == False))).scalars().all()
            targets.update(ids)
            tracker.escalated = True
        title = getattr(entity, "title", None) or "record"
        for uid in targets:
            await NotificationService(self.db).create_notification(
                organization_id=org_id, user_id=uid, category="lead", priority="high",
                title=f"SLA breach: {policy.name}",
                body=f'{metric.replace("_", " ").title()} SLA breached on "{title}".',
                link_url=f"/{tracker.entity_type}s?{tracker.entity_type}Id={tracker.entity_id}")

    async def _load_entity_actor(self, tracker: SLATracker):
        if tracker.entity_type != "lead":
            return None, None
        from app.models.lead import Lead
        lead = (await self.db.execute(select(Lead).filter(Lead.id == tracker.entity_id))).scalars().first()
        actor = None
        if lead is not None:
            uid = lead.assigned_user_id or lead.created_by
            if uid:
                actor = await self.db.get(User, uid)
        return lead, actor

    @staticmethod
    def _facts(entity) -> dict:
        f = {}
        for k in ("status", "source", "priority", "value", "score", "city", "company_name"):
            v = getattr(entity, k, None)
            f[k] = str(v) if isinstance(v, uuid.UUID) else v
        return f

    # ================= tracker/breach queries =================
    async def trackers(self, actor: User, status_filter: str | None = None, breached: bool | None = None,
                       limit: int = 50) -> list[dict]:
        q = select(SLATracker).filter(SLATracker.organization_id == actor.organization_id, SLATracker.is_deleted == False)
        if status_filter:
            q = q.filter(SLATracker.status == status_filter)
        if breached:
            q = q.filter(SLATracker.status == "breached")
        q = q.order_by(SLATracker.started_at.desc()).limit(min(limit, 200))
        return [self._tracker_dict(t) for t in (await self.db.execute(q)).scalars().all()]

    async def breaches(self, actor: User, resolved: bool | None = None, limit: int = 50) -> list[dict]:
        q = select(SLABreach).filter(SLABreach.organization_id == actor.organization_id, SLABreach.is_deleted == False)
        if resolved is not None:
            q = q.filter(SLABreach.resolved == resolved)
        q = q.order_by(SLABreach.breached_at.desc()).limit(min(limit, 200))
        return [{"id": str(b.id), "policy_id": str(b.policy_id), "entity_type": b.entity_type,
                 "entity_id": str(b.entity_id), "metric": b.metric, "hours_elapsed": b.hours_elapsed,
                 "resolved": b.resolved, "breached_at": b.breached_at.isoformat() if b.breached_at else None}
                for b in (await self.db.execute(q)).scalars().all()]

    # ================= dashboard / compliance report =================
    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        at_risk = await self._at_risk_count(actor.organization_id)
        recent = await self.trackers(actor, breached=True, limit=5)
        return {"policies": rep["policies"], "active": rep["active"], "compliance_rate": rep["compliance_rate"],
                "open_breaches": rep["open_breaches"], "at_risk": at_risk,
                "running": rep["by_status"].get("running", 0), "recent_breaches": recent}

    async def _at_risk_count(self, org_id: uuid.UUID) -> int:
        soon = _now() + timedelta(hours=2)
        return (await self.db.execute(select(func.count(SLATracker.id)).filter(
            SLATracker.organization_id == org_id, SLATracker.status == "running", SLATracker.is_deleted == False,
            SLATracker.resolution_due_at.isnot(None), SLATracker.resolution_due_at <= soon,
            SLATracker.resolution_due_at >= _now()))).scalar() or 0

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        policies = (await self.db.execute(select(func.count(SLAPolicy.id)).filter(
            SLAPolicy.organization_id == org, SLAPolicy.is_deleted == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(SLAPolicy.id)).filter(
            SLAPolicy.organization_id == org, SLAPolicy.is_deleted == False, SLAPolicy.is_active == True))).scalar() or 0
        by_status = dict((s, n) for s, n in (await self.db.execute(
            select(SLATracker.status, func.count(SLATracker.id)).filter(
                SLATracker.organization_id == org, SLATracker.is_deleted == False).group_by(SLATracker.status))).all())
        total = sum(by_status.values())
        breached = by_status.get("breached", 0)
        met = by_status.get("met", 0)
        finished = met + breached
        open_breaches = (await self.db.execute(select(func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False, SLABreach.resolved == False))).scalar() or 0
        # average response/resolution hours on finished trackers
        avg_resp = (await self.db.execute(select(func.avg(
            func.extract("epoch", SLATracker.first_response_at) - func.extract("epoch", SLATracker.started_at)
        )).filter(SLATracker.organization_id == org, SLATracker.is_deleted == False,
                  SLATracker.first_response_at.isnot(None)))).scalar()
        return {"policies": policies, "active": active, "total_trackers": total, "met": met, "breached": breached,
                "compliance_rate": round(met / finished * 100, 1) if finished else 100.0,
                "open_breaches": open_breaches, "by_status": by_status,
                "avg_response_hours": round(float(avg_resp) / 3600, 2) if avg_resp else 0.0}

    # ---------- serialize ----------
    def _policy_dict(self, p: SLAPolicy) -> dict:
        return {"id": str(p.id), "name": p.name, "description": p.description, "entity_type": p.entity_type,
                "metric": p.metric, "conditions": p.conditions, "on_breach": p.on_breach, "is_active": p.is_active,
                "breach_count": p.breach_count, "priority_field": p.priority_field, "priorities": p.priorities,
                "response_hours": p.response_hours if p.response_hours is not None else p.threshold_hours,
                "resolution_hours": p.resolution_hours, "business_hours_only": p.business_hours_only,
                "skip_holidays": p.skip_holidays, "escalate_after_hours": p.escalate_after_hours,
                "escalate_to_role": p.escalate_to_role,
                "created_at": p.created_at.isoformat() if p.created_at else None}

    def _tracker_dict(self, t: SLATracker) -> dict:
        return {"id": str(t.id), "policy_id": str(t.policy_id), "entity_type": t.entity_type,
                "entity_id": str(t.entity_id), "priority_level": t.priority_level, "status": t.status,
                "response_hours": t.response_hours, "resolution_hours": t.resolution_hours,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "response_due_at": t.response_due_at.isoformat() if t.response_due_at else None,
                "resolution_due_at": t.resolution_due_at.isoformat() if t.resolution_due_at else None,
                "first_response_at": t.first_response_at.isoformat() if t.first_response_at else None,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "response_breached": t.response_breached, "resolution_breached": t.resolution_breached,
                "breach_type": t.breach_type, "escalated": t.escalated, "paused_seconds": t.paused_seconds}


def _WEEKENDS_ONLY(hols):
    """When skip_holidays is off we still skip weekends/off-days but not holidays."""
    return []

"""Escalation Engine.

A configurable, multi-level, entity-agnostic escalation system that unifies the
scattered escalation logic (idle-lead scan, approval overdue, SLA breach) under
one rule model. An EscalationRule watches an entity type for a time-based
condition and walks an escalation chain (level 0 → manager after N hours,
level 1 → department head, …) as time passes, resolving targets from the org
hierarchy, notifying, auditing and emitting `escalation.triggered` (→ Workflows
+ Notification rules). The legacy lead/approval/SLA escalation paths are left
intact; this is additive.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.escalation import EscalationRule, EscalationEvent
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services import rule_evaluator as ev

ENTITY_TYPES = ("lead", "task", "call", "ticket", "approval")
# valid trigger conditions per entity (informational; the resolver enforces it)
TRIGGER_CONDITIONS = ("no_activity", "overdue", "unresolved", "unreturned_call", "pending")
ESCALATE_TARGETS = ("manager", "department_head", "role", "user", "skip_level_manager")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class EscalationEngineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage escalation rules.")

    @staticmethod
    def catalog() -> dict:
        return {"entity_types": list(ENTITY_TYPES), "trigger_conditions": list(TRIGGER_CONDITIONS),
                "escalate_targets": list(ESCALATE_TARGETS)}

    # ================= rule CRUD =================
    def _validate(self, data: dict):
        if data.get("entity_type") and data["entity_type"] not in ENTITY_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"entity_type must be one of {ENTITY_TYPES}")
        if data.get("trigger_condition") and data["trigger_condition"] not in TRIGGER_CONDITIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"trigger_condition must be one of {TRIGGER_CONDITIONS}")
        for lvl in (data.get("levels") or []):
            if lvl.get("after_hours") is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each level needs 'after_hours'.")
            if lvl.get("escalate_to") not in ESCALATE_TARGETS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"escalate_to must be one of {ESCALATE_TARGETS}")

    async def _get(self, actor: User, rule_id: uuid.UUID) -> EscalationRule:
        r = (await self.db.execute(select(EscalationRule).filter(
            EscalationRule.id == rule_id, EscalationRule.organization_id == actor.organization_id,
            EscalationRule.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation rule not found.")
        return r

    async def list_rules(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(EscalationRule).filter(
            EscalationRule.organization_id == actor.organization_id, EscalationRule.is_deleted == False
        ).order_by(EscalationRule.created_at.desc()))).scalars().all()
        return [self._rule_dict(r) for r in rows]

    async def create_rule(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        levels = sorted(data.get("levels") or [], key=lambda x: x.get("after_hours", 0))
        r = EscalationRule(organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
                           entity_type=data.get("entity_type") or "lead",
                           trigger_condition=data.get("trigger_condition") or "no_activity",
                           conditions=data.get("conditions"), levels=levels,
                           business_hours_only=bool(data.get("business_hours_only", False)),
                           is_active=bool(data.get("is_active", True)), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        return self._rule_dict(r)

    async def update_rule(self, actor: User, rule_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        r = await self._get(actor, rule_id)
        if "levels" in data and data["levels"] is not None:
            data["levels"] = sorted(data["levels"], key=lambda x: x.get("after_hours", 0))
        for f in ("name", "description", "entity_type", "trigger_condition", "conditions", "levels",
                  "business_hours_only", "is_active"):
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

    # ================= scan =================
    async def scan(self, org_id: uuid.UUID) -> int:
        """Evaluate every active rule; escalate overdue entities to the next due
        level. Returns escalations fired."""
        rules = (await self.db.execute(select(EscalationRule).filter(
            EscalationRule.organization_id == org_id, EscalationRule.is_active == True,
            EscalationRule.is_deleted == False))).scalars().all()
        now = _now()
        fired = 0
        for rule in rules:
            levels = rule.levels or []
            if not levels:
                continue
            candidates = await self._candidates(rule, org_id)
            rule.run_count = (rule.run_count or 0) + 1
            for entity, ref_at in candidates:
                if rule.conditions and not ev.evaluate(rule.conditions, self._facts(entity), {"now": now}):
                    continue
                ref_at = _aware(ref_at) or _aware(getattr(entity, "created_at", None)) or now
                elapsed_h = (now - ref_at).total_seconds() / 3600.0
                # highest level whose threshold has passed
                target_level = -1
                for i, lvl in enumerate(levels):
                    if elapsed_h >= float(lvl.get("after_hours", 0)):
                        target_level = i
                if target_level < 0:
                    continue
                already = (await self.db.execute(select(EscalationEvent.id).filter(
                    EscalationEvent.rule_id == rule.id, EscalationEvent.entity_id == getattr(entity, "id"),
                    EscalationEvent.level == target_level, EscalationEvent.is_deleted == False))).scalars().first()
                if already:
                    continue
                if await self._escalate(rule, levels[target_level], target_level, entity, ref_at, round(elapsed_h, 2), org_id):
                    rule.escalation_count = (rule.escalation_count or 0) + 1
                    fired += 1
            self.db.add(rule)
        await self.db.flush()
        return fired

    async def _candidates(self, rule: EscalationRule, org_id: uuid.UUID) -> list[tuple]:
        """(entity, reference_time) pairs eligible for `rule`'s condition."""
        et, cond = rule.entity_type, rule.trigger_condition
        if et == "lead":
            return await self._lead_candidates(org_id, cond)
        if et == "task":
            return await self._task_candidates(org_id)
        if et == "ticket":
            return await self._ticket_candidates(org_id)
        if et == "approval":
            return await self._approval_candidates(org_id)
        if et == "call":
            return await self._call_candidates(org_id)
        return []

    async def _lead_candidates(self, org_id, cond) -> list[tuple]:
        from app.models.lead import Lead
        from app.models.activity import Activity
        leads = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False, Lead.is_archived == False,
            Lead.converted_contact_id.is_(None)))).scalars().all()
        last_act = dict((lid, ts) for lid, ts in (await self.db.execute(
            select(Activity.lead_id, func.max(Activity.created_at)).filter(
                Activity.organization_id == org_id, Activity.lead_id.isnot(None)).group_by(Activity.lead_id))).all())
        out = []
        for lead in leads:
            if cond == "no_activity":
                ref = last_act.get(lead.id) or lead.created_at
                out.append((lead, ref))
            elif cond == "overdue":  # unassigned since creation
                if not lead.assigned_user_id:
                    out.append((lead, lead.created_at))
        return out

    async def _task_candidates(self, org_id) -> list[tuple]:
        from app.models.task import Task
        rows = (await self.db.execute(select(Task).filter(
            Task.organization_id == org_id, Task.is_deleted == False,
            Task.due_date.isnot(None), Task.status.in_(["Todo", "InProgress"])))).scalars().all()
        return [(t, t.due_date) for t in rows]

    async def _ticket_candidates(self, org_id) -> list[tuple]:
        from app.models.support_ticket import SupportTicket
        rows = (await self.db.execute(select(SupportTicket).filter(
            SupportTicket.organization_id == org_id, SupportTicket.is_deleted == False,
            SupportTicket.status.notin_(["resolved", "closed", "Resolved", "Closed"])))).scalars().all()
        return [(t, t.created_at) for t in rows]

    async def _approval_candidates(self, org_id) -> list[tuple]:
        from app.models.approval import ApprovalRequest
        rows = (await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.organization_id == org_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending"))).scalars().all()
        return [(r, r.created_at) for r in rows]

    async def _call_candidates(self, org_id) -> list[tuple]:
        """Leads whose most-recent activity is an unreturned missed/inbound call."""
        from app.models.lead import Lead
        from app.models.activity import Activity
        rows = (await self.db.execute(select(Activity).filter(
            Activity.organization_id == org_id, Activity.lead_id.isnot(None),
            Activity.activity_type == "Call",
            Activity.call_direction == "inbound"))).scalars().all()
        # keep the latest call per lead; only if no later activity of any kind
        latest_any = dict((lid, ts) for lid, ts in (await self.db.execute(
            select(Activity.lead_id, func.max(Activity.created_at)).filter(
                Activity.organization_id == org_id, Activity.lead_id.isnot(None)).group_by(Activity.lead_id))).all())
        out, seen = [], set()
        for a in sorted(rows, key=lambda x: x.created_at or _now(), reverse=True):
            if a.lead_id in seen:
                continue
            seen.add(a.lead_id)
            if _aware(latest_any.get(a.lead_id)) == _aware(a.created_at):  # this call is the latest touch
                lead = await self.db.get(Lead, a.lead_id)
                if lead and not lead.is_deleted:
                    out.append((lead, a.created_at))
        return out

    # ================= target resolution + fire =================
    async def _escalate(self, rule: EscalationRule, level_cfg: dict, level: int, entity, ref_at, elapsed_h, org_id) -> bool:
        target_type = level_cfg.get("escalate_to")
        target = await self._resolve_target(target_type, level_cfg.get("value"), entity, org_id)
        if not target:
            return False
        ev_row = EscalationEvent(organization_id=org_id, rule_id=rule.id, entity_type=rule.entity_type,
                                 entity_id=getattr(entity, "id"), level=level, escalate_to=target_type,
                                 escalated_to_user_id=target, hours_elapsed=elapsed_h, reference_at=ref_at,
                                 reason=f"{rule.trigger_condition} for {elapsed_h}h (level {level + 1})",
                                 escalated_at=_now())
        self.db.add(ev_row)
        title = getattr(entity, "title", None) or getattr(entity, "subject", None) or getattr(entity, "name", None) or "record"
        if level_cfg.get("notify", True):
            await self.notifier.create_notification(
                organization_id=org_id, user_id=target, category="system", priority="high",
                title=f"Escalation (L{level + 1}): {rule.name}",
                body=f'{rule.entity_type.title()} "{title}" escalated — {rule.trigger_condition.replace("_", " ")} for {elapsed_h}h.',
                link_url=f"/{rule.entity_type}s")
        await self.audit.log_event(organization_id=org_id, actor_user_id=None, action="ESCALATION_TRIGGERED",
                                   resource_type=rule.entity_type, resource_id=str(getattr(entity, "id")),
                                   action_metadata={"rule": rule.name, "level": level + 1, "escalated_to": str(target)})
        # emit the domain event → Workflows + Notification rules
        try:
            from app.services.event_bus import EventBus
            actor = await self.db.get(User, target)
            await EventBus(self.db).publish(
                "escalation.triggered", live_entity=entity, actor=actor,
                entity_type=rule.entity_type, entity_id=str(getattr(entity, "id")), source="system",
                trigger="escalation_triggered", organization_id=org_id,
                payload={"rule": rule.name, "level": level + 1, "condition": rule.trigger_condition,
                         "hours_elapsed": elapsed_h})
        except Exception:
            pass
        return True

    async def _resolve_target(self, target_type: str, value, entity, org_id) -> uuid.UUID | None:
        owner = (getattr(entity, "assigned_user_id", None) or getattr(entity, "assigned_to_id", None)
                 or getattr(entity, "requested_by", None) or getattr(entity, "created_by", None))
        if target_type == "user" and value:
            try:
                return uuid.UUID(str(value))
            except (ValueError, TypeError):
                return None
        if target_type == "role" and value:
            return (await self.db.execute(select(User.id).filter(
                User.organization_id == org_id, User.role == value, User.is_active == True,
                User.is_deleted == False))).scalars().first()
        if target_type == "manager" and owner:
            return (await self.db.execute(select(User.reporting_to_id).filter(User.id == owner))).scalar()
        if target_type == "skip_level_manager" and owner:
            mgr = (await self.db.execute(select(User.reporting_to_id).filter(User.id == owner))).scalar()
            if mgr:
                return (await self.db.execute(select(User.reporting_to_id).filter(User.id == mgr))).scalar()
            return None
        if target_type == "department_head" and owner:
            dept_id = (await self.db.execute(select(User.department_id).filter(User.id == owner))).scalar()
            if dept_id:
                from app.models.department import Department
                return (await self.db.execute(select(Department.head_user_id).filter(Department.id == dept_id))).scalar()
        return None

    @staticmethod
    def _facts(entity) -> dict:
        f = {}
        for k in ("status", "source", "priority", "value", "score", "amount", "request_type"):
            v = getattr(entity, k, None)
            f[k] = str(v) if isinstance(v, uuid.UUID) else v
        return f

    # ================= events / dashboard / reports =================
    async def events(self, actor: User, rule_id: uuid.UUID | None = None, entity_type: str | None = None,
                     limit: int = 50) -> list[dict]:
        q = select(EscalationEvent).filter(EscalationEvent.organization_id == actor.organization_id,
                                           EscalationEvent.is_deleted == False)
        if rule_id:
            q = q.filter(EscalationEvent.rule_id == rule_id)
        if entity_type:
            q = q.filter(EscalationEvent.entity_type == entity_type)
        q = q.order_by(EscalationEvent.escalated_at.desc()).limit(min(limit, 200))
        return [self._event_dict(e) for e in (await self.db.execute(q)).scalars().all()]

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        rules = (await self.db.execute(select(func.count(EscalationRule.id)).filter(
            EscalationRule.organization_id == org, EscalationRule.is_deleted == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(EscalationRule.id)).filter(
            EscalationRule.organization_id == org, EscalationRule.is_deleted == False,
            EscalationRule.is_active == True))).scalar() or 0
        total = (await self.db.execute(select(func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False))).scalar() or 0
        by_entity = dict((k, v) for k, v in (await self.db.execute(
            select(EscalationEvent.entity_type, func.count(EscalationEvent.id)).filter(
                EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False
            ).group_by(EscalationEvent.entity_type))).all())
        by_level = dict((str(k + 1), v) for k, v in (await self.db.execute(
            select(EscalationEvent.level, func.count(EscalationEvent.id)).filter(
                EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False
            ).group_by(EscalationEvent.level))).all())
        return {"rules": rules, "active": active, "escalations": total,
                "by_entity": by_entity, "by_level": by_level}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        week = _now() - timedelta(days=7)
        recent_count = (await self.db.execute(select(func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == actor.organization_id, EscalationEvent.is_deleted == False,
            EscalationEvent.escalated_at >= week))).scalar() or 0
        recent = await self.events(actor, limit=5)
        return {"rules": rep["rules"], "active": rep["active"], "escalations": rep["escalations"],
                "last_7_days": recent_count, "by_entity": rep["by_entity"], "recent": recent}

    # ---------- serialize ----------
    def _rule_dict(self, r: EscalationRule) -> dict:
        return {"id": str(r.id), "name": r.name, "description": r.description, "entity_type": r.entity_type,
                "trigger_condition": r.trigger_condition, "conditions": r.conditions, "levels": r.levels,
                "business_hours_only": r.business_hours_only, "is_active": r.is_active,
                "run_count": r.run_count, "escalation_count": r.escalation_count,
                "created_at": r.created_at.isoformat() if r.created_at else None}

    def _event_dict(self, e: EscalationEvent) -> dict:
        return {"id": str(e.id), "rule_id": str(e.rule_id), "entity_type": e.entity_type,
                "entity_id": str(e.entity_id), "level": e.level + 1, "escalate_to": e.escalate_to,
                "escalated_to_user_id": str(e.escalated_to_user_id) if e.escalated_to_user_id else None,
                "reason": e.reason, "hours_elapsed": e.hours_elapsed,
                "escalated_at": e.escalated_at.isoformat() if e.escalated_at else None}

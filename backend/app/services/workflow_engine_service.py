"""Workflow Orchestration Engine.

An additive, multi-step, versioned workflow engine that ORCHESTRATES the
existing modules — it does not redesign them. The legacy single-rule
WorkflowService keeps working untouched; this engine subscribes to the same
trigger events via a single additive `dispatch()` hook inside WorkflowService.run().

A workflow is a visual graph — nodes (trigger/action/branch/merge/delay/loop/
approval/end) connected by edges — with a lifecycle (draft → published),
immutable version snapshots (rollback), execution history + per-node logs, and a
dry-run testing mode. Actions reuse existing services (tasks, calendar, sms,
whatsapp, email, notifications, approvals).
"""
from __future__ import annotations
import copy
import json
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workflow import (
    Workflow, WorkflowVersion, WorkflowExecution, WorkflowExecutionStep,
    WORKFLOW_STATUSES, NODE_TYPES,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

# Full trigger catalog (legacy + orchestration-only). entity_type per trigger.
TRIGGER_ENTITY = {
    "lead_created": "lead", "lead_updated": "lead", "lead_converted": "lead",
    "call_logged": "lead", "call_disposition": "lead",
    "follow_up_created": "lead", "follow_up_missed": "lead",
    "meeting_scheduled": "lead", "site_visit_scheduled": "lead",
    "sms_received": "lead", "whatsapp_received": "lead", "email_received": "lead",
    "sms_sent": "lead", "whatsapp_sent": "lead", "email_sent": "lead",
    "contact_created": "contact", "contact_updated": "contact",
    "task_created": "task", "task_updated": "task", "task_completed": "task",
    "invoice_created": "customer", "payment_received": "customer",
    "attendance_marked": "attendance", "late_login": "attendance",
    "leave_applied": "leave", "leave_approved": "leave",
    "shift_assigned": "shift", "goal_achieved": "performance",
    "approval_approved": "approval", "approval_rejected": "approval",
    "user_created": "user", "sla_breached": "lead", "escalation_triggered": "generic",
    "manual": "generic",
}
TRIGGERS = tuple(TRIGGER_ENTITY.keys())
# Action node action-types the engine can execute.
ACTIONS = (
    "assign_lead", "assign_task", "update_status", "create_task", "schedule_meeting",
    "send_email", "send_sms", "send_whatsapp", "create_notification", "webhook",
)
CATEGORIES = ("Sales", "Onboarding", "Support", "HR", "Finance", "Operations", "General")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowEngineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage workflows.")

    @staticmethod
    def catalog() -> dict:
        return {
            "triggers": [{"event": t, "entity_type": e} for t, e in TRIGGER_ENTITY.items()],
            "actions": list(ACTIONS),
            "node_types": list(NODE_TYPES),
            "categories": list(CATEGORIES),
            "statuses": list(WORKFLOW_STATUSES),
        }

    # ================= CRUD / lifecycle =================
    async def _get(self, actor: User, workflow_id: uuid.UUID) -> Workflow:
        w = (await self.db.execute(select(Workflow).filter(
            Workflow.id == workflow_id, Workflow.organization_id == actor.organization_id,
            Workflow.is_deleted == False))).scalars().first()
        if not w:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return w

    def _validate_graph(self, trigger_event: str, graph: dict) -> dict:
        if trigger_event not in TRIGGER_ENTITY:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid trigger_event. Allowed: {sorted(TRIGGER_ENTITY)}")
        graph = graph or {}
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        ids = set()
        has_trigger = False
        for n in nodes:
            nid, ntype = n.get("id"), n.get("type")
            if not nid or ntype not in NODE_TYPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid node: {n}")
            if nid in ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Duplicate node id {nid}")
            ids.add(nid)
            if ntype == "trigger":
                has_trigger = True
            if ntype == "action" and (n.get("config") or {}).get("action") not in ACTIONS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Invalid action type: {(n.get('config') or {}).get('action')}")
        if nodes and not has_trigger:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Graph needs a trigger node.")
        for e in edges:
            if e.get("from") not in ids or e.get("to") not in ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edge references unknown node.")
        return {"nodes": nodes, "edges": edges}

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        trigger = data["trigger_event"]
        graph = self._validate_graph(trigger, data.get("graph") or {"nodes": [], "edges": []})
        w = Workflow(organization_id=actor.organization_id, name=data["name"],
                     description=data.get("description"), category=data.get("category"),
                     status="draft", version=1, is_enabled=bool(data.get("is_enabled", True)),
                     is_template=bool(data.get("is_template", False)), trigger_event=trigger,
                     entity_type=TRIGGER_ENTITY[trigger], graph=graph, created_by=actor.id)
        self.db.add(w)
        await self.db.flush()
        await self.db.refresh(w)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="WORKFLOW_CREATED", resource_type="workflow", resource_id=str(w.id),
                                   action_metadata={"name": w.name})
        return await self._serialize(w)

    async def update(self, actor: User, workflow_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        if "trigger_event" in data and data["trigger_event"]:
            if data["trigger_event"] not in TRIGGER_ENTITY:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trigger_event.")
            w.trigger_event = data["trigger_event"]
            w.entity_type = TRIGGER_ENTITY[data["trigger_event"]]
        if "graph" in data and data["graph"] is not None:
            w.graph = self._validate_graph(w.trigger_event, data["graph"])
            # editing a published workflow drops it back to draft and opens a NEW
            # version number so re-publishing snapshots distinctly from the last one
            if w.status == "published":
                w.status = "draft"
                w.version = w.version + 1
        for f in ("name", "description", "category", "is_enabled", "is_template"):
            if f in data and data[f] is not None:
                setattr(w, f, data[f])
        self.db.add(w)
        await self.db.flush()
        await self.db.refresh(w)
        return await self._serialize(w)

    async def delete(self, actor: User, workflow_id: uuid.UUID) -> None:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        w.is_deleted = True
        self.db.add(w)
        await self.db.flush()

    async def publish(self, actor: User, workflow_id: uuid.UUID, notes: str | None = None) -> dict:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        if not (w.graph or {}).get("nodes"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot publish an empty workflow.")
        # snapshot the current graph as the published version (idempotent: re-publishing
        # an unchanged version bumps to a fresh number rather than colliding)
        existing = (await self.db.execute(select(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == w.id, WorkflowVersion.version == w.version,
            WorkflowVersion.is_deleted == False))).scalars().first()
        if existing is not None:
            w.version = w.version + 1
        self.db.add(WorkflowVersion(organization_id=actor.organization_id, workflow_id=w.id, version=w.version,
                                    trigger_event=w.trigger_event, graph=w.graph, notes=notes,
                                    published_by=actor.id, published_at=_now()))
        w.status = "published"
        self.db.add(w)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="WORKFLOW_PUBLISHED", resource_type="workflow", resource_id=str(w.id),
                                   action_metadata={"version": w.version})
        return await self._serialize(w)

    async def set_enabled(self, actor: User, workflow_id: uuid.UUID, enabled: bool) -> dict:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        w.is_enabled = enabled
        self.db.add(w)
        await self.db.flush()
        return await self._serialize(w)

    async def clone(self, actor: User, workflow_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        c = Workflow(organization_id=actor.organization_id, name=f"{w.name} (copy)",
                     description=w.description, category=w.category, status="draft", version=1,
                     is_enabled=False, is_template=False, trigger_event=w.trigger_event,
                     entity_type=w.entity_type, graph=copy.deepcopy(w.graph), created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return await self._serialize(c)

    # ---------- versions / rollback ----------
    async def versions(self, actor: User, workflow_id: uuid.UUID) -> list[dict]:
        await self._get(actor, workflow_id)
        rows = list((await self.db.execute(select(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.is_deleted == False)
            .order_by(WorkflowVersion.version.desc()))).scalars().all())
        names = await self._names({r.published_by for r in rows})
        return [{"id": str(r.id), "version": r.version, "trigger_event": r.trigger_event, "notes": r.notes,
                 "published_by_name": names.get(r.published_by),
                 "published_at": r.published_at.isoformat() if r.published_at else None} for r in rows]

    async def rollback(self, actor: User, workflow_id: uuid.UUID, version: int) -> dict:
        """Restore a prior published version's graph as a new draft revision."""
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        v = (await self.db.execute(select(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.version == version,
            WorkflowVersion.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        w.graph = copy.deepcopy(v.graph)
        w.trigger_event = v.trigger_event
        w.entity_type = TRIGGER_ENTITY.get(v.trigger_event, "lead")
        w.version = w.version + 1
        w.status = "draft"
        self.db.add(w)
        await self.db.flush()
        await self.db.refresh(w)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="WORKFLOW_ROLLED_BACK", resource_type="workflow", resource_id=str(w.id),
                                   action_metadata={"restored_version": version})
        return await self._serialize(w)

    # ---------- import / export ----------
    async def export_one(self, actor: User, workflow_id: uuid.UUID) -> dict:
        w = await self._get(actor, workflow_id)
        return {"name": w.name, "description": w.description, "category": w.category,
                "trigger_event": w.trigger_event, "graph": w.graph, "is_template": w.is_template,
                "_format": "crm.workflow.v1"}

    async def import_one(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        if not data.get("name") or not data.get("trigger_event"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import needs name and trigger_event.")
        return await self.create(actor, {"name": data["name"], "description": data.get("description"),
                                         "category": data.get("category"), "trigger_event": data["trigger_event"],
                                         "graph": data.get("graph") or {"nodes": [], "edges": []},
                                         "is_template": bool(data.get("is_template", False)), "is_enabled": False})

    # ---------- listing ----------
    async def list(self, actor: User, category=None, status_filter=None, is_template=None, trigger=None) -> list[dict]:
        q = select(Workflow).filter(Workflow.organization_id == actor.organization_id, Workflow.is_deleted == False)
        if category:
            q = q.filter(Workflow.category == category)
        if status_filter:
            q = q.filter(Workflow.status == status_filter)
        if is_template is not None:
            q = q.filter(Workflow.is_template == is_template)
        if trigger:
            q = q.filter(Workflow.trigger_event == trigger)
        rows = list((await self.db.execute(q.order_by(Workflow.created_at.desc()))).scalars().all())
        return [await self._serialize(w) for w in rows]

    async def get(self, actor: User, workflow_id: uuid.UUID) -> dict:
        return await self._serialize(await self._get(actor, workflow_id), full=True)

    # ================= Templates =================
    async def seed_templates(self, actor: User) -> dict:
        self._require_manager(actor)
        created = 0
        for tpl in _BUILTIN_TEMPLATES:
            exists = (await self.db.execute(select(Workflow.id).filter(
                Workflow.organization_id == actor.organization_id, Workflow.is_template == True,
                Workflow.name == tpl["name"], Workflow.is_deleted == False))).scalar()
            if exists:
                continue
            graph = self._validate_graph(tpl["trigger_event"], tpl["graph"])
            self.db.add(Workflow(organization_id=actor.organization_id, name=tpl["name"],
                                 description=tpl["description"], category=tpl["category"], status="draft",
                                 version=1, is_enabled=False, is_template=True, trigger_event=tpl["trigger_event"],
                                 entity_type=TRIGGER_ENTITY[tpl["trigger_event"]], graph=graph, created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"created": created}

    async def instantiate_template(self, actor: User, workflow_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        if not w.is_template:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a template.")
        c = Workflow(organization_id=actor.organization_id, name=w.name, description=w.description,
                     category=w.category, status="draft", version=1, is_enabled=True, is_template=False,
                     trigger_event=w.trigger_event, entity_type=w.entity_type, graph=copy.deepcopy(w.graph),
                     created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return await self._serialize(c)

    # ================= Dispatch + execution =================
    async def dispatch(self, trigger_event: str, entity, actor: User, entity_type: str) -> None:
        """Called additively from WorkflowService.run(). Runs every published,
        enabled, non-template workflow for this trigger against the entity.
        Best-effort — never raises into the caller."""
        try:
            org_id = getattr(entity, "organization_id", None)
            if org_id is None:
                return
            workflows = list((await self.db.execute(select(Workflow).filter(
                Workflow.organization_id == org_id, Workflow.is_deleted == False,
                Workflow.status == "published", Workflow.is_enabled == True,
                Workflow.is_template == False, Workflow.trigger_event == trigger_event))).scalars().all())
            for w in workflows:
                await self._execute(w, entity, actor, entity_type, is_test=False)
        except Exception:
            # orchestration must never break the originating action
            return

    async def test_run(self, actor: User, workflow_id: uuid.UUID) -> dict:
        """Dry run: walk the graph, log what WOULD happen, mutate nothing / send
        nothing. Uses a synthetic context so it works without a real entity."""
        self._require_manager(actor)
        w = await self._get(actor, workflow_id)
        ex = await self._execute(w, _TestEntity(actor.organization_id, actor.id), actor, w.entity_type, is_test=True)
        return ex

    async def _execute(self, w: Workflow, entity, actor: User, entity_type: str, is_test: bool) -> dict:
        graph = w.graph or {}
        nodes = {n["id"]: n for n in graph.get("nodes") or []}
        edges = graph.get("edges") or []
        # top-level condition on the trigger node (optional)
        trigger_node = next((n for n in nodes.values() if n.get("type") == "trigger"), None)
        if not trigger_node:
            return {"skipped": True}
        if not is_test:
            trigger_conds = await self._effective_conditions(trigger_node, w.organization_id)
            if not self._match_conditions(entity, trigger_conds):
                return {"skipped": True}

        ex = WorkflowExecution(organization_id=w.organization_id, workflow_id=w.id, version=w.version,
                               trigger_event=w.trigger_event, entity_type=entity_type,
                               entity_id=str(getattr(entity, "id", "")) or None,
                               status="test" if is_test else "completed", is_test=is_test,
                               triggered_by=getattr(actor, "id", None), started_at=_now())
        self.db.add(ex)
        await self.db.flush()

        seq = 0
        steps_run = 0
        error = None
        # walk from the trigger's outgoing edge
        cur = self._next_node(trigger_node["id"], None, edges)
        guard = 0
        loop_counts: dict[str, int] = {}
        try:
            while cur and cur in nodes and guard < 200:
                guard += 1
                node = nodes[cur]
                ntype = node.get("type")
                cfg = node.get("config") or {}
                branch_taken = None
                if ntype == "end":
                    await self._log(ex, seq, node, "success", "Workflow ended"); seq += 1
                    break
                if ntype == "merge":
                    await self._log(ex, seq, node, "success", "Merge"); seq += 1
                    cur = self._next_node(cur, None, edges); continue
                if ntype == "delay":
                    mins = int(cfg.get("minutes", 0) or 0)
                    await self._log(ex, seq, node, "success", f"Delay {mins}m (scheduler seam — continues in sync mode)")
                    seq += 1
                    cur = self._next_node(cur, None, edges); continue
                if ntype == "loop":
                    n_id = node["id"]
                    limit = int(cfg.get("iterations", 1) or 1)
                    loop_counts[n_id] = loop_counts.get(n_id, 0) + 1
                    await self._log(ex, seq, node, "success", f"Loop iteration {loop_counts[n_id]}/{limit}"); seq += 1
                    if loop_counts[n_id] < limit:
                        cur = self._next_node(cur, "loop", edges) or self._next_node(cur, None, edges)
                    else:
                        cur = self._next_node(cur, "exit", edges) or self._next_node(cur, None, edges)
                    continue
                if ntype == "branch":
                    branch_conds = await self._effective_conditions(node, w.organization_id)
                    ok = self._match_conditions(entity, branch_conds) if not is_test else True
                    branch_taken = "true" if ok else "false"
                    await self._log(ex, seq, node, "success", f"Branch → {branch_taken}"); seq += 1
                    cur = self._next_node(cur, branch_taken, edges) or self._next_node(cur, None, edges); continue
                if ntype == "approval":
                    await self._apply_approval_node(ex, seq, node, entity, actor, is_test); seq += 1; steps_run += 1
                    cur = self._next_node(cur, None, edges); continue
                if ntype == "action":
                    await self._apply_action_node(ex, seq, node, entity, actor, is_test); seq += 1; steps_run += 1
                    cur = self._next_node(cur, None, edges); continue
                # unknown node type — skip
                await self._log(ex, seq, node, "skipped", f"Unhandled node type {ntype}"); seq += 1
                cur = self._next_node(cur, None, edges)
        except Exception as e:  # pragma: no cover - defensive
            error = str(e)
            ex.status = "failed"

        ex.steps_run = steps_run
        ex.error = error
        ex.finished_at = _now()
        if error and ex.status != "failed":
            ex.status = "failed"
        self.db.add(ex)
        await self.db.flush()
        if not is_test:
            await self.audit.log_event(organization_id=w.organization_id, actor_user_id=getattr(actor, "id", None),
                                       action="WORKFLOW_RUN", resource_type="workflow", resource_id=str(w.id),
                                       action_metadata={"execution_id": str(ex.id), "steps": steps_run})
        return await self._serialize_execution(ex, with_steps=True)

    def _next_node(self, from_id: str, branch: str | None, edges: list) -> str | None:
        for e in edges:
            if e.get("from") == from_id and (e.get("branch") or None) == (branch or None):
                return e.get("to")
        if branch is not None:
            # fall back to an unlabelled edge
            for e in edges:
                if e.get("from") == from_id and not e.get("branch"):
                    return e.get("to")
        return None

    # ---------- condition matching (reuses the legacy matcher semantics) ----------
    @staticmethod
    def _is_group(conditions) -> bool:
        """A nested expression tree (Rule Engine format) vs. the flat legacy list."""
        if isinstance(conditions, dict):
            return conditions.get("type") == "group" or "children" in conditions
        if isinstance(conditions, list):
            return any(isinstance(c, dict) and (c.get("type") == "group" or "children" in c)
                       for c in conditions)
        return False

    def _facts_for(self, entity, fields: set) -> dict:
        facts = {}
        for f in fields:
            # only direct attributes are resolvable synchronously; cross-entity
            # dotted facts are the RuleService's domain (async traversal).
            val = getattr(entity, f, None) if "." not in f else None
            if isinstance(val, uuid.UUID):
                val = str(val)
            facts[f] = val
        return facts

    def _match_conditions(self, entity, conditions) -> bool:
        if not conditions:
            return True
        # New Rule-Engine expression tree (AND/OR/NOT, rich ops, date/time,
        # dynamic variables) → delegate to the shared pure evaluator.
        if self._is_group(conditions):
            from app.services import rule_evaluator as ev
            facts = self._facts_for(entity, ev.collect_fields(conditions))
            return ev.evaluate(conditions, facts, {"now": _now()})
        # Legacy flat list (unchanged behaviour for backward compatibility).
        from app.services.workflow_service import _coerce_number
        for c in conditions:
            field, op, expected = c.get("field"), c.get("op"), c.get("value")
            actual = getattr(entity, field, None)
            if actual is not None and field in ("stage_id", "company_id", "kpi_id"):
                actual = str(actual)
            ok = False
            if op in ("gt", "gte", "lt", "lte"):
                a, e = _coerce_number(actual), _coerce_number(expected)
                ok = a is not None and e is not None and {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[op]
            elif op == "eq":
                ok = str(actual) == str(expected)
            elif op == "neq":
                ok = str(actual) != str(expected)
            elif op == "contains":
                ok = expected is not None and actual is not None and str(expected).lower() in str(actual).lower()
            if not ok:
                return False
        return True

    async def _effective_conditions(self, node: dict, org_id):
        """Resolve a node's conditions — inline conditions, or the definition of
        a saved Rule referenced by `rule_id` (reusable rules across workflows)."""
        cfg = node.get("config") or {}
        rid = cfg.get("rule_id")
        if rid:
            from app.models.rule import Rule
            try:
                ruuid = uuid.UUID(str(rid))
            except (ValueError, TypeError):
                return cfg.get("conditions") or []
            rule = (await self.db.execute(select(Rule).filter(
                Rule.id == ruuid, Rule.organization_id == org_id,
                Rule.is_deleted == False))).scalars().first()
            if rule is not None:
                return rule.definition
        return cfg.get("conditions") or []

    # ---------- action node executor (reuses existing modules) ----------
    async def _apply_action_node(self, ex, seq, node, entity, actor, is_test):
        cfg = node.get("config") or {}
        action = cfg.get("action")
        org = ex.organization_id
        if is_test:
            await self._log(ex, seq, node, "success", f"[test] would run {action}", action_type=action)
            return
        try:
            if action == "update_status" and hasattr(entity, "status") and cfg.get("value"):
                old = getattr(entity, "status", None)
                entity.status = str(cfg["value"])
                self.db.add(entity)
                await self._log(ex, seq, node, "success", f"status → {cfg['value']}", action_type=action,
                                reverse={"entity_type": ex.entity_type, "entity_id": ex.entity_id,
                                         "field": "status", "old_value": old})
                return
            if action in ("assign_lead", "assign_task") and hasattr(entity, "assigned_user_id") and cfg.get("user_id"):
                old = str(getattr(entity, "assigned_user_id", None)) if getattr(entity, "assigned_user_id", None) else None
                entity.assigned_user_id = uuid.UUID(str(cfg["user_id"]))
                self.db.add(entity)
                await self._log(ex, seq, node, "success", action, action_type=action,
                                reverse={"entity_type": ex.entity_type, "entity_id": ex.entity_id,
                                         "field": "assigned_user_id", "old_value": old})
                return
            if action == "create_notification":
                target = cfg.get("user_id") or getattr(entity, "assigned_user_id", None) or getattr(entity, "user_id", None)
                if target:
                    await self.notifier.create_notification(
                        organization_id=org, user_id=uuid.UUID(str(target)), category="workflow",
                        title=cfg.get("title") or "Workflow notification",
                        body=cfg.get("message") or "A workflow notified you.", link_url="/workflows")
                    await self._log(ex, seq, node, "success", "notification created", action_type=action)
                    return
                await self._log(ex, seq, node, "skipped", "no notification target", action_type=action)
                return
            if action == "create_task":
                from app.models.task import Task
                t = Task(organization_id=org, title=cfg.get("title") or "Workflow task",
                         description=cfg.get("message"), status="Todo",
                         assigned_user_id=(uuid.UUID(str(cfg["user_id"])) if cfg.get("user_id")
                                           else getattr(entity, "assigned_user_id", None)),
                         created_by=getattr(actor, "id", None))
                self.db.add(t)
                await self._log(ex, seq, node, "success", "task created", action_type=action)
                return
            if action == "schedule_meeting":
                from app.models.calendar_event import CalendarEvent
                start = _now() + timedelta(days=1)
                ev = CalendarEvent(organization_id=org, title=cfg.get("title") or "Workflow meeting",
                                   event_type="Meeting", start_at=start, end_at=start + timedelta(hours=1),
                                   assigned_user_id=(uuid.UUID(str(cfg["user_id"])) if cfg.get("user_id")
                                                     else getattr(entity, "assigned_user_id", None)),
                                   created_by=getattr(actor, "id", None),
                                   lead_id=getattr(entity, "id", None) if ex.entity_type == "lead" else None)
                self.db.add(ev)
                await self._log(ex, seq, node, "success", "meeting scheduled", action_type=action)
                return
            if action in ("send_sms", "send_whatsapp", "send_email"):
                # Best-effort outbound via the messaging modules; swallow provider errors.
                phone = getattr(entity, "phone", None)
                email = getattr(entity, "email", None)
                sent = "skipped"
                try:
                    if action == "send_sms" and phone:
                        from app.services.sms_service import SmsService
                        await SmsService(self.db).send(actor, {"body": cfg.get("message") or "", "to_number": phone,
                                                                "lead_id": getattr(entity, "id", None)}, _skip_cap=True)
                        sent = "success"
                    elif action == "send_whatsapp" and phone:
                        from app.services.whatsapp_service import WhatsAppService
                        await WhatsAppService(self.db).send_text(actor, {"body": cfg.get("message") or "",
                                                                         "to_number": phone, "lead_id": getattr(entity, "id", None)})
                        sent = "success"
                    elif action == "send_email" and email:
                        from app.services.email_service_module import EmailModuleService
                        await EmailModuleService(self.db).send(actor, {"subject": cfg.get("title") or "Message",
                                                                       "body": cfg.get("message") or "", "to": email,
                                                                       "lead_id": getattr(entity, "id", None)})
                        sent = "success"
                except Exception:
                    sent = "failed"
                await self._log(ex, seq, node, sent, action, action_type=action)
                return
            if action == "webhook":
                url = cfg.get("url")
                delivered = "skipped"
                if url:
                    try:
                        import httpx
                        async with httpx.AsyncClient(timeout=5) as client:
                            await client.post(url, json={"trigger": ex.trigger_event,
                                                         "entity_type": ex.entity_type, "entity_id": ex.entity_id})
                        delivered = "success"
                    except Exception:
                        delivered = "failed"
                await self._log(ex, seq, node, delivered, f"webhook {url}", action_type=action)
                return
            await self._log(ex, seq, node, "skipped", f"{action}: not applicable to {ex.entity_type}", action_type=action)
        except Exception as e:
            await self._log(ex, seq, node, "failed", str(e)[:400], action_type=action)

    async def _apply_approval_node(self, ex, seq, node, entity, actor, is_test):
        cfg = node.get("config") or {}
        if is_test:
            await self._log(ex, seq, node, "success", "[test] would raise an approval request", action_type="approval")
            return
        try:
            from app.services.approval_service import ApprovalService
            await ApprovalService(self.db).create_request(actor, {
                "request_type": cfg.get("request_type") or "generic",
                "title": cfg.get("title") or f"Workflow approval ({ex.trigger_event})",
                "description": cfg.get("message"), "amount": cfg.get("amount"),
                "reference_type": ex.entity_type, "reference_id": ex.entity_id})
            await self._log(ex, seq, node, "success", "approval request created", action_type="approval")
        except Exception as e:
            await self._log(ex, seq, node, "failed", str(e)[:400], action_type="approval")

    async def _log(self, ex, seq, node, status_val, detail, action_type=None, reverse=None):
        self.db.add(WorkflowExecutionStep(organization_id=ex.organization_id, execution_id=ex.id, seq=seq,
                                          node_id=node.get("id"), node_type=node.get("type"),
                                          action_type=action_type, status=status_val, detail=detail[:500] if detail else None,
                                          reverse=reverse))
        await self.db.flush()

    # ================= Executions / logs / rollback =================
    async def executions(self, actor: User, workflow_id=None, is_test=None, skip=0, limit=50) -> dict:
        q = select(WorkflowExecution).filter(WorkflowExecution.organization_id == actor.organization_id,
                                             WorkflowExecution.is_deleted == False)
        if workflow_id:
            q = q.filter(WorkflowExecution.workflow_id == workflow_id)
        if is_test is not None:
            q = q.filter(WorkflowExecution.is_test == is_test)
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(WorkflowExecution.started_at.desc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize_execution(r) for r in rows], "total": total}

    async def execution_logs(self, actor: User, execution_id: uuid.UUID) -> dict:
        ex = (await self.db.execute(select(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id, WorkflowExecution.organization_id == actor.organization_id,
            WorkflowExecution.is_deleted == False))).scalars().first()
        if not ex:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        return await self._serialize_execution(ex, with_steps=True)

    async def rollback_execution(self, actor: User, execution_id: uuid.UUID) -> dict:
        """Undo a completed run by reversing each mutating step's recorded change."""
        self._require_manager(actor)
        ex = (await self.db.execute(select(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id, WorkflowExecution.organization_id == actor.organization_id,
            WorkflowExecution.is_deleted == False))).scalars().first()
        if not ex:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        if ex.is_test or ex.rolled_back:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nothing to roll back.")
        steps = list((await self.db.execute(select(WorkflowExecutionStep).filter(
            WorkflowExecutionStep.execution_id == ex.id, WorkflowExecutionStep.is_deleted == False)
            .order_by(WorkflowExecutionStep.seq.desc()))).scalars().all())
        reverted = 0
        for s in steps:
            rev = s.reverse
            if not rev:
                continue
            reverted += await self._revert(rev)
        ex.rolled_back = True
        self.db.add(ex)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="WORKFLOW_EXECUTION_ROLLED_BACK", resource_type="workflow",
                                   resource_id=str(ex.workflow_id), action_metadata={"execution_id": str(ex.id), "reverted": reverted})
        return {"reverted": reverted}

    async def _revert(self, rev: dict) -> int:
        et, eid, field, old = rev.get("entity_type"), rev.get("entity_id"), rev.get("field"), rev.get("old_value")
        model = {"lead": "Lead", "task": "Task", "contact": "Contact"}.get(et)
        if not model or not eid:
            return 0
        from app.models import lead as _l, task as _t, contact as _c
        cls = {"Lead": _l.Lead, "Task": _t.Task, "Contact": _c.Contact}[model]
        obj = (await self.db.execute(select(cls).filter(cls.id == uuid.UUID(str(eid))))).scalars().first()
        if not obj:
            return 0
        if field == "assigned_user_id":
            setattr(obj, field, uuid.UUID(str(old)) if old else None)
        else:
            setattr(obj, field, old)
        self.db.add(obj)
        await self.db.flush()
        return 1

    # ================= Reports =================
    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        total_wf = (await self.db.execute(select(func.count(Workflow.id)).filter(
            Workflow.organization_id == org, Workflow.is_deleted == False, Workflow.is_template == False))).scalar() or 0
        published = (await self.db.execute(select(func.count(Workflow.id)).filter(
            Workflow.organization_id == org, Workflow.is_deleted == False, Workflow.is_template == False,
            Workflow.status == "published"))).scalar() or 0
        enabled = (await self.db.execute(select(func.count(Workflow.id)).filter(
            Workflow.organization_id == org, Workflow.is_deleted == False, Workflow.is_template == False,
            Workflow.status == "published", Workflow.is_enabled == True))).scalar() or 0
        ex_rows = (await self.db.execute(select(WorkflowExecution.status, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False).group_by(WorkflowExecution.status))).all()
        by_status = {s: n for s, n in ex_rows}
        runs = sum(by_status.values())
        # top workflows by executions
        top = (await self.db.execute(select(WorkflowExecution.workflow_id, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False).group_by(WorkflowExecution.workflow_id)
            .order_by(func.count(WorkflowExecution.id).desc()).limit(5))).all()
        names = {w.id: w.name for w in (await self.db.execute(select(Workflow).filter(
            Workflow.organization_id == org))).scalars().all()}
        return {"total_workflows": total_wf, "published": published, "enabled": enabled,
                "total_runs": runs, "completed": by_status.get("completed", 0), "failed": by_status.get("failed", 0),
                "success_rate": round(by_status.get("completed", 0) * 100 / runs, 1) if runs else 0.0,
                "top_workflows": [{"workflow_id": str(wid), "name": names.get(wid, "?"), "runs": n} for wid, n in top]}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        recent = (await self.executions(actor, is_test=False, limit=5))["items"]
        return {"published": rep["published"], "enabled": rep["enabled"], "total_runs": rep["total_runs"],
                "success_rate": rep["success_rate"], "failed": rep["failed"], "recent": recent}

    # ---------- helpers ----------
    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _serialize(self, w: Workflow, full: bool = False) -> dict:
        node_count = len((w.graph or {}).get("nodes") or [])
        d = {"id": str(w.id), "name": w.name, "description": w.description, "category": w.category,
             "status": w.status, "version": w.version, "is_enabled": w.is_enabled, "is_template": w.is_template,
             "trigger_event": w.trigger_event, "entity_type": w.entity_type, "node_count": node_count,
             "created_at": w.created_at}
        if full:
            d["graph"] = w.graph
        return d

    async def _serialize_execution(self, ex: WorkflowExecution, with_steps: bool = False) -> dict:
        wf = (await self.db.execute(select(Workflow.name).filter(Workflow.id == ex.workflow_id))).scalar()
        d = {"id": str(ex.id), "workflow_id": str(ex.workflow_id), "workflow_name": wf,
             "version": ex.version, "trigger_event": ex.trigger_event, "entity_type": ex.entity_type,
             "entity_id": ex.entity_id, "status": ex.status, "is_test": ex.is_test, "rolled_back": ex.rolled_back,
             "steps_run": ex.steps_run, "error": ex.error,
             "started_at": ex.started_at.isoformat() if ex.started_at else None,
             "finished_at": ex.finished_at.isoformat() if ex.finished_at else None}
        if with_steps:
            steps = list((await self.db.execute(select(WorkflowExecutionStep).filter(
                WorkflowExecutionStep.execution_id == ex.id, WorkflowExecutionStep.is_deleted == False)
                .order_by(WorkflowExecutionStep.seq.asc()))).scalars().all())
            d["steps"] = [{"seq": s.seq, "node_id": s.node_id, "node_type": s.node_type,
                           "action_type": s.action_type, "status": s.status, "detail": s.detail} for s in steps]
        return d


class _TestEntity:
    """Synthetic entity for testing-mode dry runs (no real record needed)."""
    def __init__(self, organization_id, user_id):
        self.organization_id = organization_id
        self.id = None
        self.assigned_user_id = user_id
        self.user_id = user_id
        self.status = "New"
        self.phone = None
        self.email = None


# Built-in workflow templates seeded on demand.
_BUILTIN_TEMPLATES = [
    {"name": "New Lead — notify & task", "description": "When a lead is created, notify the owner and create a follow-up task.",
     "category": "Sales", "trigger_event": "lead_created",
     "graph": {"nodes": [
         {"id": "t1", "type": "trigger", "config": {"conditions": []}},
         {"id": "a1", "type": "action", "config": {"action": "create_notification", "title": "New lead", "message": "A new lead was assigned."}},
         {"id": "a2", "type": "action", "config": {"action": "create_task", "title": "Follow up with new lead"}},
         {"id": "e1", "type": "end", "config": {}},
     ], "edges": [{"from": "t1", "to": "a1"}, {"from": "a1", "to": "a2"}, {"from": "a2", "to": "e1"}]}},
    {"name": "High-value lead approval", "description": "Branch on lead value; request approval for big deals.",
     "category": "Sales", "trigger_event": "lead_updated",
     "graph": {"nodes": [
         {"id": "t1", "type": "trigger", "config": {"conditions": []}},
         {"id": "b1", "type": "branch", "config": {"conditions": [{"field": "value", "op": "gte", "value": 100000}]}},
         {"id": "ap", "type": "approval", "config": {"request_type": "discount", "title": "High-value lead review"}},
         {"id": "e1", "type": "end", "config": {}},
     ], "edges": [{"from": "t1", "to": "b1"}, {"from": "b1", "to": "ap", "branch": "true"},
                  {"from": "b1", "to": "e1", "branch": "false"}, {"from": "ap", "to": "e1"}]}},
    {"name": "Payment received — thank you", "description": "On payment, notify and email a thank-you.",
     "category": "Finance", "trigger_event": "payment_received",
     "graph": {"nodes": [
         {"id": "t1", "type": "trigger", "config": {"conditions": []}},
         {"id": "a1", "type": "action", "config": {"action": "create_notification", "title": "Payment received"}},
         {"id": "e1", "type": "end", "config": {}},
     ], "edges": [{"from": "t1", "to": "a1"}, {"from": "a1", "to": "e1"}]}},
]

"""Rule Engine service.

Manages reusable, named, prioritised boolean rules and evaluates them against
CRM entities via the pure `rule_evaluator`. This is the missing layer on top of
the existing flat-condition matching: nested AND/OR/NOT expression trees, a rich
operator set, date/time/dynamic-variable conditions, cross-entity fact
resolution (user/department), rule templates, testing, priority-based conflict
resolution, and reporting.

Additive: nothing here mutates entities. The workflow engine and legacy
lead-automation keep their own action execution; they may *reference* a saved
rule for its condition tree, but rules themselves are evaluation-only.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.rule import Rule, RuleEvaluation
from app.services.audit_service import AuditService
from app.services import rule_evaluator as ev

# Entity types a rule can target, with the resolvable fact fields surfaced to the
# expression builder. Dotted keys are cross-entity facts filled by build_facts.
ENTITY_FIELDS: dict[str, list[dict]] = {
    "lead": [
        {"field": "status", "type": "string"},
        {"field": "source", "type": "string"},
        {"field": "priority", "type": "string"},
        {"field": "value", "type": "number"},
        {"field": "score", "type": "number"},
        {"field": "city", "type": "string"},
        {"field": "company_name", "type": "string"},
        {"field": "email", "type": "string"},
        {"field": "phone", "type": "string"},
        {"field": "pin_code", "type": "string"},
        {"field": "call_attempts_count", "type": "number"},
        {"field": "is_archived", "type": "bool"},
        {"field": "created_at", "type": "date"},
        {"field": "converted_at", "type": "date"},
        {"field": "stage_id", "type": "id"},
        {"field": "assigned_user_id", "type": "id"},
        # cross-entity (assigned user)
        {"field": "assigned_user.role", "type": "string", "cross": True},
        {"field": "assigned_user.department_id", "type": "id", "cross": True},
        {"field": "assigned_user.is_active", "type": "bool", "cross": True},
        {"field": "department.name", "type": "string", "cross": True},
        {"field": "department.code", "type": "string", "cross": True},
    ],
    "contact": [
        {"field": "first_name", "type": "string"}, {"field": "last_name", "type": "string"},
        {"field": "email", "type": "string"}, {"field": "phone", "type": "string"},
        {"field": "job_title", "type": "string"}, {"field": "company_id", "type": "id"},
        {"field": "created_at", "type": "date"},
        {"field": "assigned_user.role", "type": "string", "cross": True},
    ],
    "task": [
        {"field": "status", "type": "string"}, {"field": "priority", "type": "string"},
        {"field": "assigned_user_id", "type": "id"}, {"field": "recurrence", "type": "string"},
        {"field": "due_date", "type": "date"}, {"field": "created_at", "type": "date"},
        {"field": "assigned_user.role", "type": "string", "cross": True},
    ],
    "attendance": [
        {"field": "status", "type": "string"}, {"field": "is_late", "type": "bool"},
        {"field": "late_minutes", "type": "number"}, {"field": "shift_id", "type": "id"},
        {"field": "work_date", "type": "date"}, {"field": "check_in_time", "type": "time"},
    ],
    "leave": [
        {"field": "status", "type": "string"}, {"field": "request_type", "type": "string"},
        {"field": "leave_type_id", "type": "id"}, {"field": "day_count", "type": "number"},
        {"field": "is_half_day", "type": "bool"}, {"field": "start_date", "type": "date"},
    ],
    "approval": [
        {"field": "request_type", "type": "string"}, {"field": "amount", "type": "number"},
        {"field": "status", "type": "string"},
    ],
    "performance": [
        {"field": "kpi_id", "type": "id"}, {"field": "attainment", "type": "number"},
    ],
    "user": [
        {"field": "role", "type": "string"}, {"field": "is_active", "type": "bool"},
        {"field": "department_id", "type": "id"}, {"field": "email", "type": "string"},
        {"field": "created_at", "type": "date"},
        {"field": "department.name", "type": "string", "cross": True},
    ],
}
ENTITY_TYPES = tuple(ENTITY_FIELDS.keys())
CONFLICT_STRATEGIES = ("highest_priority", "first_match", "all")
CATEGORIES = ("Lead Scoring", "Routing", "Escalation", "Qualification", "Compliance", "General")

# A few ready-to-use rule templates (seeded on demand, like workflow templates).
_BUILTIN_TEMPLATES = [
    {
        "name": "High-value hot lead", "category": "Lead Scoring", "entity_type": "lead",
        "description": "Deal value ≥ 50,000 AND (status is New OR Contacted).",
        "priority": 200,
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value": 50000},
            {"type": "group", "logic": "or", "children": [
                {"type": "condition", "field": "status", "op": "eq", "value": "New"},
                {"type": "condition", "field": "status", "op": "eq", "value": "Contacted"},
            ]},
        ]},
    },
    {
        "name": "Stale lead (no touch in 14 days)", "category": "Escalation", "entity_type": "lead",
        "description": "Created more than 14 days ago and NOT already converted.",
        "priority": 150,
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "created_at", "op": "date_older_than_days", "value": 14},
            {"type": "condition", "field": "converted_at", "op": "is_empty"},
        ]},
    },
    {
        "name": "Unassigned inbound lead", "category": "Routing", "entity_type": "lead",
        "description": "No owner yet and source is a web/inbound channel.",
        "priority": 120,
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "assigned_user_id", "op": "is_empty"},
            {"type": "condition", "field": "source", "op": "in", "value": "Website,Inbound,Web Form"},
        ]},
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RuleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage rules.")

    @staticmethod
    def catalog() -> dict:
        return {
            "entity_types": list(ENTITY_TYPES),
            "fields": ENTITY_FIELDS,
            "operators": {
                "comparison": list(ev.COMPARISON_OPS),
                "date": list(ev.DATE_OPS),
                "time": list(ev.TIME_OPS),
                "boolean": list(ev.BOOL_OPS),
            },
            "logic": list(ev.LOGIC_OPS),
            "variables": list(ev.VARIABLES),
            "value_types": ["static", "field", "variable"],
            "conflict_strategies": list(CONFLICT_STRATEGIES),
            "categories": list(CATEGORIES),
        }

    # ---------- validation ----------
    def _validate(self, entity_type: str, definition, conflict_strategy: str | None = None):
        if entity_type not in ENTITY_FIELDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid entity_type. Allowed: {sorted(ENTITY_TYPES)}")
        if conflict_strategy and conflict_strategy not in CONFLICT_STRATEGIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid conflict_strategy. Allowed: {list(CONFLICT_STRATEGIES)}")
        allowed = {f["field"] for f in ENTITY_FIELDS[entity_type]}
        self._validate_node(ev._normalize(definition), allowed, depth=0)

    def _validate_node(self, node: dict, allowed: set, depth: int):
        if depth > 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rule nesting too deep (max 10).")
        if node.get("type") == "group" or "children" in node:
            logic = (node.get("logic") or "and").lower()
            if logic not in ev.LOGIC_OPS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid logic: {logic}")
            for c in (node.get("children") or []):
                self._validate_node(c, allowed, depth + 1)
            return
        field, op = node.get("field"), node.get("op")
        if field not in allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Field '{field}' is not valid for this entity.")
        if op not in ev.ALL_OPS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid operator: {op}")
        vt = node.get("value_type") or "static"
        if vt == "field" and node.get("value_field") not in allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Comparison field '{node.get('value_field')}' is not valid for this entity.")
        if vt == "variable" and node.get("variable") not in ev.VARIABLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid variable: {node.get('variable')}")

    # ---------- CRUD ----------
    async def _get(self, actor: User, rule_id: uuid.UUID) -> Rule:
        r = (await self.db.execute(select(Rule).filter(
            Rule.id == rule_id, Rule.organization_id == actor.organization_id,
            Rule.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        return r

    async def list_rules(self, actor: User, entity_type: str | None = None,
                         is_template: bool | None = None, active_only: bool = False) -> list[dict]:
        q = select(Rule).filter(Rule.organization_id == actor.organization_id, Rule.is_deleted == False)
        if entity_type:
            q = q.filter(Rule.entity_type == entity_type)
        if is_template is not None:
            q = q.filter(Rule.is_template == is_template)
        if active_only:
            q = q.filter(Rule.is_active == True)
        # execution order: priority desc, then newest — the deterministic order
        # conflict resolution relies on.
        q = q.order_by(Rule.priority.desc(), Rule.created_at.desc())
        rows = (await self.db.execute(q)).scalars().all()
        return [self._serialize(r) for r in rows]

    async def get(self, actor: User, rule_id: uuid.UUID) -> dict:
        return self._serialize(await self._get(actor, rule_id))

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        entity_type = data.get("entity_type") or "lead"
        self._validate(entity_type, data.get("definition"), data.get("conflict_strategy"))
        r = Rule(organization_id=actor.organization_id, name=data["name"],
                 description=data.get("description"), category=data.get("category"),
                 entity_type=entity_type, definition=data.get("definition") or {"type": "group", "logic": "and", "children": []},
                 priority=int(data.get("priority", 100)),
                 conflict_strategy=data.get("conflict_strategy") or "highest_priority",
                 is_active=bool(data.get("is_active", True)),
                 is_template=bool(data.get("is_template", False)), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_CREATED", resource_type="rule", resource_id=str(r.id),
                                   action_metadata={"name": r.name, "entity_type": r.entity_type})
        return self._serialize(r)

    async def update(self, actor: User, rule_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        entity_type = data.get("entity_type") or r.entity_type
        if "definition" in data or "entity_type" in data or "conflict_strategy" in data:
            self._validate(entity_type, data.get("definition", r.definition),
                           data.get("conflict_strategy", r.conflict_strategy))
        for f in ("name", "description", "category", "entity_type", "definition",
                  "priority", "conflict_strategy", "is_active", "is_template"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_UPDATED", resource_type="rule", resource_id=str(r.id),
                                   action_metadata={"name": r.name})
        return self._serialize(r)

    async def delete(self, actor: User, rule_id: uuid.UUID) -> None:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        r.is_deleted = True
        self.db.add(r)
        await self.db.flush()

    async def clone(self, actor: User, rule_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        src = await self._get(actor, rule_id)
        return await self.create(actor, {
            "name": f"{src.name} (copy)", "description": src.description, "category": src.category,
            "entity_type": src.entity_type, "definition": src.definition, "priority": src.priority,
            "conflict_strategy": src.conflict_strategy, "is_active": False, "is_template": False,
        })

    async def set_priority(self, actor: User, rule_id: uuid.UUID, priority: int) -> dict:
        return await self.update(actor, rule_id, {"priority": int(priority)})

    # ---------- fact resolution (cross-entity) ----------
    async def build_facts(self, entity, entity_type: str, fields: set | None = None) -> dict:
        """Flatten an entity into a fact map the evaluator can read, resolving
        the cross-entity dotted fields (assigned_user.*, department.*) that a
        rule references. Only loads related rows when actually needed."""
        facts: dict = {}
        for spec in ENTITY_FIELDS.get(entity_type, []):
            f = spec["field"]
            if "." in f:
                continue  # cross-entity handled below
            val = getattr(entity, f, None)
            if isinstance(val, uuid.UUID):
                val = str(val)
            facts[f] = val
        needed = fields if fields is not None else {s["field"] for s in ENTITY_FIELDS.get(entity_type, [])}

        # assigned user traversal (lead/contact/task)
        if any(n.startswith("assigned_user.") or n.startswith("department.") for n in needed):
            user = None
            uid = getattr(entity, "assigned_user_id", None) or (
                entity.id if entity_type == "user" else None)
            if uid:
                user = (await self.db.execute(select(User).filter(User.id == uid))).scalars().first()
            if user is not None:
                facts["assigned_user.role"] = user.role
                facts["assigned_user.is_active"] = user.is_active
                facts["assigned_user.department_id"] = str(user.department_id) if user.department_id else None
            # department traversal (via the resolved user, or the entity itself)
            if any(n.startswith("department.") for n in needed):
                dept_id = getattr(entity, "department_id", None) or (user.department_id if user else None)
                if dept_id:
                    from app.models.department import Department
                    dept = (await self.db.execute(select(Department).filter(
                        Department.id == dept_id))).scalars().first()
                    if dept is not None:
                        facts["department.name"] = dept.name
                        facts["department.code"] = getattr(dept, "code", None)
        return facts

    # ---------- evaluation / testing ----------
    async def evaluate_rule(self, actor: User, rule: Rule, entity, *, is_test: bool = False,
                            entity_id=None, log: bool = True) -> dict:
        fields = ev.collect_fields(rule.definition)
        facts = await self.build_facts(entity, rule.entity_type, fields)
        ctx = {"now": _now(), "current_user_id": actor.id}
        result = ev.evaluate_trace(rule.definition, facts, ctx)
        # counters (cheap live reporting)
        rule.eval_count = (rule.eval_count or 0) + 1
        if result["matched"]:
            rule.match_count = (rule.match_count or 0) + 1
        rule.last_evaluated_at = _now()
        self.db.add(rule)
        if log:
            self.db.add(RuleEvaluation(
                organization_id=rule.organization_id, rule_id=rule.id,
                entity_type=rule.entity_type,
                entity_id=(entity_id or getattr(entity, "id", None)) if not is_test else None,
                matched=result["matched"], is_test=is_test, trace=result["trace"],
                evaluated_by=actor.id))
        await self.db.flush()
        return {"rule_id": str(rule.id), "name": rule.name,
                "matched": result["matched"], "trace": result["trace"], "facts": facts}

    async def test(self, actor: User, rule_id: uuid.UUID, sample: dict | None = None,
                   entity_id: uuid.UUID | None = None) -> dict:
        """Test a rule against either an explicit sample fact dict or a real
        entity by id — a dry run that records a test evaluation."""
        self._require_manager(actor)
        rule = await self._get(actor, rule_id)
        if entity_id is not None:
            entity = await self._load_entity(actor, rule.entity_type, entity_id)
            return await self.evaluate_rule(actor, rule, entity, is_test=True, entity_id=entity_id)
        # sample path: evaluate directly against the provided facts (no traversal)
        facts = dict(sample or {})
        ctx = {"now": _now(), "current_user_id": actor.id}
        result = ev.evaluate_trace(rule.definition, facts, ctx)
        rule.eval_count = (rule.eval_count or 0) + 1
        if result["matched"]:
            rule.match_count = (rule.match_count or 0) + 1
        rule.last_evaluated_at = _now()
        self.db.add(rule)
        self.db.add(RuleEvaluation(organization_id=rule.organization_id, rule_id=rule.id,
                                   entity_type=rule.entity_type, entity_id=None,
                                   matched=result["matched"], is_test=True, trace=result["trace"],
                                   evaluated_by=actor.id))
        await self.db.flush()
        return {"rule_id": str(rule.id), "name": rule.name, "matched": result["matched"],
                "trace": result["trace"], "facts": facts}

    async def _load_entity(self, actor: User, entity_type: str, entity_id: uuid.UUID):
        model = {
            "lead": "app.models.lead.Lead", "contact": "app.models.contact.Contact",
            "task": "app.models.task.Task", "user": "app.models.user.User",
            "attendance": "app.models.attendance.AttendanceRecord",
            "leave": "app.models.leave.LeaveRequest",
        }.get(entity_type)
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Testing against a live {entity_type} entity is not supported.")
        mod_path, cls = model.rsplit(".", 1)
        import importlib
        Model = getattr(importlib.import_module(mod_path), cls)
        obj = (await self.db.execute(select(Model).filter(
            Model.id == entity_id, Model.organization_id == actor.organization_id))).scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_type} not found")
        return obj

    async def resolve(self, actor: User, entity_type: str, entity, strategy: str | None = None) -> dict:
        """Evaluate all active rules for an entity and pick winner(s) by the
        conflict-resolution strategy. Used by callers that want 'which rules
        apply' semantics (priority ordering + conflict resolution)."""
        rows = (await self.db.execute(select(Rule).filter(
            Rule.organization_id == actor.organization_id, Rule.entity_type == entity_type,
            Rule.is_active == True, Rule.is_template == False, Rule.is_deleted == False
        ).order_by(Rule.priority.desc(), Rule.created_at.desc()))).scalars().all()
        matched: list[dict] = []
        for r in rows:
            res = await self.evaluate_rule(actor, r, entity, log=False)
            if res["matched"]:
                matched.append({"rule_id": str(r.id), "name": r.name, "priority": r.priority,
                                "conflict_strategy": r.conflict_strategy})
        strat = strategy or (matched[0]["conflict_strategy"] if matched else "highest_priority")
        if not matched:
            winner = None
        elif strat == "all":
            winner = matched
        else:  # highest_priority == first_match given the deterministic ordering
            winner = matched[0]
        return {"matched": matched, "strategy": strat, "winner": winner}

    # ---------- templates ----------
    async def seed_templates(self, actor: User) -> dict:
        self._require_manager(actor)
        created = 0
        for tpl in _BUILTIN_TEMPLATES:
            exists = (await self.db.execute(select(Rule).filter(
                Rule.organization_id == actor.organization_id, Rule.name == tpl["name"],
                Rule.is_template == True, Rule.is_deleted == False))).scalars().first()
            if exists:
                continue
            self.db.add(Rule(organization_id=actor.organization_id, name=tpl["name"],
                             description=tpl.get("description"), category=tpl.get("category"),
                             entity_type=tpl["entity_type"], definition=tpl["definition"],
                             priority=tpl.get("priority", 100), conflict_strategy="highest_priority",
                             is_active=False, is_template=True, created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"created": created}

    async def instantiate_template(self, actor: User, rule_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        tpl = await self._get(actor, rule_id)
        return await self.create(actor, {
            "name": f"{tpl.name}", "description": tpl.description, "category": tpl.category,
            "entity_type": tpl.entity_type, "definition": tpl.definition, "priority": tpl.priority,
            "conflict_strategy": tpl.conflict_strategy, "is_active": True, "is_template": False,
        })

    # ---------- import / export ----------
    async def export_one(self, actor: User, rule_id: uuid.UUID) -> dict:
        r = await self._get(actor, rule_id)
        return {"_format": "crm.rule.v1", "name": r.name, "description": r.description,
                "category": r.category, "entity_type": r.entity_type, "definition": r.definition,
                "priority": r.priority, "conflict_strategy": r.conflict_strategy}

    async def import_one(self, actor: User, payload: dict) -> dict:
        self._require_manager(actor)
        if payload.get("_format") != "crm.rule.v1":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unrecognised rule export format.")
        return await self.create(actor, {
            "name": payload.get("name") or "Imported rule", "description": payload.get("description"),
            "category": payload.get("category"), "entity_type": payload.get("entity_type") or "lead",
            "definition": payload.get("definition"), "priority": payload.get("priority", 100),
            "conflict_strategy": payload.get("conflict_strategy") or "highest_priority",
            "is_active": False, "is_template": False,
        })

    # ---------- evaluation history / reports ----------
    async def evaluations(self, actor: User, rule_id: uuid.UUID | None = None, limit: int = 50) -> list[dict]:
        q = select(RuleEvaluation).filter(RuleEvaluation.organization_id == actor.organization_id,
                                          RuleEvaluation.is_deleted == False)
        if rule_id:
            q = q.filter(RuleEvaluation.rule_id == rule_id)
        q = q.order_by(RuleEvaluation.created_at.desc()).limit(min(limit, 200))
        rows = (await self.db.execute(q)).scalars().all()
        return [{"id": str(e.id), "rule_id": str(e.rule_id), "entity_type": e.entity_type,
                 "entity_id": str(e.entity_id) if e.entity_id else None, "matched": e.matched,
                 "is_test": e.is_test, "created_at": e.created_at.isoformat() if e.created_at else None}
                for e in rows]

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        total = (await self.db.execute(select(func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False,
            Rule.is_active == True))).scalar() or 0
        templates = (await self.db.execute(select(func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == True))).scalar() or 0
        evals = (await self.db.execute(select(func.count(RuleEvaluation.id)).filter(
            RuleEvaluation.organization_id == org, RuleEvaluation.is_deleted == False))).scalar() or 0
        matches = (await self.db.execute(select(func.count(RuleEvaluation.id)).filter(
            RuleEvaluation.organization_id == org, RuleEvaluation.is_deleted == False,
            RuleEvaluation.matched == True))).scalar() or 0
        by_entity = (await self.db.execute(select(Rule.entity_type, func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False
        ).group_by(Rule.entity_type))).all()
        return {"total": total, "active": active, "inactive": total - active, "templates": templates,
                "evaluations": evals, "matches": matches,
                "match_rate": round(matches / evals * 100, 1) if evals else 0.0,
                "by_entity": {k: v for k, v in by_entity}}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        top = (await self.db.execute(select(Rule).filter(
            Rule.organization_id == actor.organization_id, Rule.is_deleted == False,
            Rule.is_template == False, Rule.is_active == True
        ).order_by(Rule.match_count.desc(), Rule.priority.desc()).limit(5))).scalars().all()
        return {"total": rep["total"], "active": rep["active"], "match_rate": rep["match_rate"],
                "evaluations": rep["evaluations"],
                "top": [{"id": str(r.id), "name": r.name, "entity_type": r.entity_type,
                         "priority": r.priority, "match_count": r.match_count} for r in top]}

    # ---------- serialize ----------
    def _serialize(self, r: Rule) -> dict:
        def _count(node) -> int:
            if isinstance(node, dict) and (node.get("type") == "group" or "children" in node):
                return sum(_count(c) for c in (node.get("children") or []))
            return 1
        return {"id": str(r.id), "organization_id": str(r.organization_id), "name": r.name,
                "description": r.description, "category": r.category, "entity_type": r.entity_type,
                "definition": r.definition, "priority": r.priority,
                "conflict_strategy": r.conflict_strategy, "is_active": r.is_active,
                "is_template": r.is_template, "condition_count": _count(ev._normalize(r.definition)),
                "match_count": r.match_count, "eval_count": r.eval_count,
                "last_evaluated_at": r.last_evaluated_at.isoformat() if r.last_evaluated_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None}

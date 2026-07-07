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
from app.models.rule_designer import RuleComponent, RuleVariable, RuleVersion
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services import rule_evaluator as ev

# Actions a matched rule can run (if-this-then-that). Deliberately non-destructive
# and entity-agnostic — they notify people, so a single set works for every
# entity_type. The workflow engine remains the place for entity-mutating actions.
ACTION_TYPES = ("notify_owner", "notify_manager", "notify_role", "notify_user")
VARIABLE_VALUE_TYPES = ("string", "number", "bool", "date")
MAX_COMPONENT_DEPTH = 8

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
        self.notifier = NotificationService(db)

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
            "action_types": list(ACTION_TYPES),
            "variable_value_types": list(VARIABLE_VALUE_TYPES),
        }

    # ---------- validation ----------
    def _validate(self, entity_type: str, definition, conflict_strategy: str | None = None,
                  allowed_vars: set | None = None):
        if entity_type not in ENTITY_FIELDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid entity_type. Allowed: {sorted(ENTITY_TYPES)}")
        if conflict_strategy and conflict_strategy not in CONFLICT_STRATEGIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid conflict_strategy. Allowed: {list(CONFLICT_STRATEGIES)}")
        allowed = {f["field"] for f in ENTITY_FIELDS[entity_type]}
        vars_ok = set(ev.VARIABLES) | (allowed_vars or set())
        self._validate_node(ev._normalize(definition), allowed, vars_ok, depth=0)

    def _validate_node(self, node: dict, allowed: set, allowed_vars: set, depth: int):
        if depth > 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rule nesting too deep (max 10).")
        if node.get("type") == "group" or "children" in node:
            logic = (node.get("logic") or "and").lower()
            if logic not in ev.LOGIC_OPS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid logic: {logic}")
            for c in (node.get("children") or []):
                self._validate_node(c, allowed, allowed_vars, depth + 1)
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
        if vt == "variable" and node.get("variable") not in allowed_vars:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid variable: {node.get('variable')}")

    def _validate_actions(self, actions) -> list:
        if actions in (None, []):
            return []
        if not isinstance(actions, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="actions must be a list.")
        out = []
        for a in actions:
            t = (a or {}).get("type")
            if t not in ACTION_TYPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Invalid action type '{t}'. Allowed: {list(ACTION_TYPES)}")
            if t == "notify_user" and not a.get("user_id"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="notify_user needs a user_id.")
            if t == "notify_role" and not a.get("role"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="notify_role needs a role.")
            out.append({k: (str(v) if k == "user_id" and v else v) for k, v in a.items()})
        return out

    async def _user_var_names(self, org_id) -> set:
        rows = (await self.db.execute(select(RuleVariable.name).filter(
            RuleVariable.organization_id == org_id, RuleVariable.is_deleted == False))).scalars().all()
        return set(rows)

    async def _prepare_definition(self, actor: User, entity_type: str, definition,
                                  conflict_strategy: str | None = None):
        """Expand any component refs, then validate the resulting tree against the
        entity's fields and the org's variables. Returns nothing; raises on error."""
        expanded = await self._expand_definition(actor.organization_id, definition, entity_type)
        allowed_vars = await self._user_var_names(actor.organization_id)
        self._validate(entity_type, expanded, conflict_strategy, allowed_vars=allowed_vars)

    # ---------- reusable component expansion ----------
    async def _expand_definition(self, org_id, definition, entity_type: str,
                                 _seen: frozenset = frozenset(), _depth: int = 0):
        """Recursively replace {"type":"ref","ref_id":...} nodes with the referenced
        component's definition. Guards against cycles and runaway depth."""
        node = ev._normalize(definition)
        return await self._expand_node(org_id, node, entity_type, _seen, _depth)

    async def _expand_node(self, org_id, node, entity_type, seen, depth):
        if depth > MAX_COMPONENT_DEPTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Component nesting too deep (possible cycle).")
        if not isinstance(node, dict):
            return node
        if node.get("type") == "ref":
            ref_id = node.get("ref_id")
            if not ref_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A ref node needs a ref_id.")
            ref_key = str(ref_id)
            if ref_key in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Circular component reference detected.")
            try:
                ref_uuid = uuid.UUID(ref_key)
            except (ValueError, AttributeError, TypeError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A ref node needs a valid ref_id.")
            comp = (await self.db.execute(select(RuleComponent).filter(
                RuleComponent.id == ref_uuid, RuleComponent.organization_id == org_id,
                RuleComponent.is_deleted == False))).scalars().first()
            if not comp:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Referenced component {ref_id} not found.")
            if comp.entity_type != entity_type:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Component '{comp.name}' targets {comp.entity_type}, not {entity_type}.")
            return await self._expand_node(org_id, ev._normalize(comp.definition), entity_type,
                                           seen | {ref_key}, depth + 1)
        if node.get("type") == "group" or "children" in node:
            children = []
            for c in (node.get("children") or []):
                children.append(await self._expand_node(org_id, c, entity_type, seen, depth + 1))
            return {"type": "group", "logic": node.get("logic") or "and", "children": children}
        return node

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
        await self._prepare_definition(actor, entity_type, data.get("definition"), data.get("conflict_strategy"))
        actions = self._validate_actions(data.get("actions"))
        r = Rule(organization_id=actor.organization_id, name=data["name"],
                 description=data.get("description"), category=data.get("category"),
                 entity_type=entity_type, definition=data.get("definition") or {"type": "group", "logic": "and", "children": []},
                 actions=actions or None, priority=int(data.get("priority", 100)),
                 conflict_strategy=data.get("conflict_strategy") or "highest_priority",
                 is_active=bool(data.get("is_active", True)),
                 is_template=bool(data.get("is_template", False)), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self._snapshot(actor, r, note="created")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_CREATED", resource_type="rule", resource_id=str(r.id),
                                   action_metadata={"name": r.name, "entity_type": r.entity_type})
        return self._serialize(r)

    async def update(self, actor: User, rule_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        entity_type = data.get("entity_type") or r.entity_type
        if "definition" in data or "entity_type" in data or "conflict_strategy" in data:
            await self._prepare_definition(actor, entity_type, data.get("definition", r.definition),
                                           data.get("conflict_strategy", r.conflict_strategy))
        if "actions" in data:
            r.actions = self._validate_actions(data.get("actions")) or None
        # snapshot the pre-change state so it can be rolled back to
        structural = any(k in data for k in ("definition", "actions", "entity_type", "conflict_strategy", "priority"))
        if structural:
            await self._snapshot(actor, r, note="before update")
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
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_DELETED", resource_type="rule", resource_id=str(r.id),
                                   action_metadata={"name": r.name})

    async def clone(self, actor: User, rule_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        src = await self._get(actor, rule_id)
        return await self.create(actor, {
            "name": f"{src.name} (copy)", "description": src.description, "category": src.category,
            "entity_type": src.entity_type, "definition": src.definition, "actions": src.actions,
            "priority": src.priority, "conflict_strategy": src.conflict_strategy,
            "is_active": False, "is_template": False,
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
        definition = await self._expand_definition(rule.organization_id, rule.definition, rule.entity_type)
        fields = ev.collect_fields(definition)
        facts = await self.build_facts(entity, rule.entity_type, fields)
        ctx = {"now": _now(), "current_user_id": actor.id,
               "user_vars": await self._resolved_user_vars(rule.organization_id)}
        result = ev.evaluate_trace(definition, facts, ctx)
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
        definition = await self._expand_definition(rule.organization_id, rule.definition, rule.entity_type)
        ctx = {"now": _now(), "current_user_id": actor.id,
               "user_vars": await self._resolved_user_vars(rule.organization_id)}
        result = ev.evaluate_trace(definition, facts, ctx)
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
            "entity_type": tpl.entity_type, "definition": tpl.definition, "actions": tpl.actions,
            "priority": tpl.priority, "conflict_strategy": tpl.conflict_strategy,
            "is_active": True, "is_template": False,
        })

    # ---------- import / export ----------
    async def export_one(self, actor: User, rule_id: uuid.UUID) -> dict:
        r = await self._get(actor, rule_id)
        return {"_format": "crm.rule.v1", "name": r.name, "description": r.description,
                "category": r.category, "entity_type": r.entity_type, "definition": r.definition,
                "actions": r.actions, "priority": r.priority, "conflict_strategy": r.conflict_strategy}

    async def import_one(self, actor: User, payload: dict) -> dict:
        self._require_manager(actor)
        if payload.get("_format") != "crm.rule.v1":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unrecognised rule export format.")
        return await self.create(actor, {
            "name": payload.get("name") or "Imported rule", "description": payload.get("description"),
            "category": payload.get("category"), "entity_type": payload.get("entity_type") or "lead",
            "definition": payload.get("definition"), "actions": payload.get("actions"),
            "priority": payload.get("priority", 100),
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

    # ---------- variables (org-defined named constants) ----------
    @staticmethod
    def _coerce_var(value: str | None, value_type: str):
        if value is None:
            return None
        if value_type == "number":
            try:
                f = float(value)
                return int(f) if f.is_integer() else f
            except (TypeError, ValueError):
                return None
        if value_type == "bool":
            return str(value).strip().lower() in ("true", "1", "yes")
        return value  # string / date kept as text (evaluator's date ops parse strings)

    async def _resolved_user_vars(self, org_id) -> dict:
        rows = (await self.db.execute(select(RuleVariable).filter(
            RuleVariable.organization_id == org_id, RuleVariable.is_deleted == False))).scalars().all()
        return {v.name: self._coerce_var(v.value, v.value_type) for v in rows}

    async def list_variables(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(RuleVariable).filter(
            RuleVariable.organization_id == actor.organization_id, RuleVariable.is_deleted == False
        ).order_by(RuleVariable.name.asc()))).scalars().all()
        return [self._serialize_variable(v) for v in rows]

    async def create_variable(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variable name is required.")
        vt = data.get("value_type") or "string"
        if vt not in VARIABLE_VALUE_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"value_type must be one of {list(VARIABLE_VALUE_TYPES)}")
        dup = (await self.db.execute(select(RuleVariable).filter(
            RuleVariable.organization_id == actor.organization_id, RuleVariable.name == name,
            RuleVariable.is_deleted == False))).scalars().first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A variable named '{name}' already exists.")
        v = RuleVariable(organization_id=actor.organization_id, name=name, description=data.get("description"),
                         value_type=vt, value=(str(data["value"]) if data.get("value") is not None else None),
                         created_by=actor.id)
        self.db.add(v)
        await self.db.flush()
        await self.db.refresh(v)
        return self._serialize_variable(v)

    async def update_variable(self, actor: User, var_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        v = (await self.db.execute(select(RuleVariable).filter(
            RuleVariable.id == var_id, RuleVariable.organization_id == actor.organization_id,
            RuleVariable.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variable not found")
        if "value_type" in data and data["value_type"]:
            if data["value_type"] not in VARIABLE_VALUE_TYPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"value_type must be one of {list(VARIABLE_VALUE_TYPES)}")
            v.value_type = data["value_type"]
        if "description" in data:
            v.description = data["description"]
        if "value" in data:
            v.value = str(data["value"]) if data["value"] is not None else None
        self.db.add(v)
        await self.db.flush()
        await self.db.refresh(v)
        return self._serialize_variable(v)

    async def delete_variable(self, actor: User, var_id: uuid.UUID) -> None:
        self._require_manager(actor)
        v = (await self.db.execute(select(RuleVariable).filter(
            RuleVariable.id == var_id, RuleVariable.organization_id == actor.organization_id,
            RuleVariable.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variable not found")
        v.is_deleted = True
        self.db.add(v)
        await self.db.flush()

    def _serialize_variable(self, v: RuleVariable) -> dict:
        return {"id": str(v.id), "name": v.name, "description": v.description,
                "value_type": v.value_type, "value": v.value,
                "resolved": self._coerce_var(v.value, v.value_type),
                "created_at": v.created_at.isoformat() if v.created_at else None}

    # ---------- reusable components ----------
    async def list_components(self, actor: User, entity_type: str | None = None) -> list[dict]:
        q = select(RuleComponent).filter(RuleComponent.organization_id == actor.organization_id,
                                         RuleComponent.is_deleted == False)
        if entity_type:
            q = q.filter(RuleComponent.entity_type == entity_type)
        rows = (await self.db.execute(q.order_by(RuleComponent.name.asc()))).scalars().all()
        return [self._serialize_component(c) for c in rows]

    async def create_component(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        entity_type = data.get("entity_type") or "lead"
        await self._prepare_definition(actor, entity_type, data.get("definition"))
        c = RuleComponent(organization_id=actor.organization_id, name=data["name"],
                          description=data.get("description"), entity_type=entity_type,
                          definition=data.get("definition") or {"type": "group", "logic": "and", "children": []},
                          is_active=bool(data.get("is_active", True)), created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_COMPONENT_CREATED", resource_type="rule_component",
                                   resource_id=str(c.id), action_metadata={"name": c.name})
        return self._serialize_component(c)

    async def update_component(self, actor: User, comp_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        c = (await self.db.execute(select(RuleComponent).filter(
            RuleComponent.id == comp_id, RuleComponent.organization_id == actor.organization_id,
            RuleComponent.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
        entity_type = data.get("entity_type") or c.entity_type
        if "definition" in data or "entity_type" in data:
            await self._prepare_definition(actor, entity_type, data.get("definition", c.definition))
        for f in ("name", "description", "entity_type", "definition", "is_active"):
            if f in data and data[f] is not None:
                setattr(c, f, data[f])
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return self._serialize_component(c)

    async def delete_component(self, actor: User, comp_id: uuid.UUID) -> None:
        self._require_manager(actor)
        c = (await self.db.execute(select(RuleComponent).filter(
            RuleComponent.id == comp_id, RuleComponent.organization_id == actor.organization_id,
            RuleComponent.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
        c.is_deleted = True
        self.db.add(c)
        await self.db.flush()

    def _serialize_component(self, c: RuleComponent) -> dict:
        return {"id": str(c.id), "name": c.name, "description": c.description,
                "entity_type": c.entity_type, "definition": c.definition, "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None}

    # ---------- versioning ----------
    async def _snapshot(self, actor: User, rule: Rule, note: str | None = None) -> None:
        last = (await self.db.execute(select(func.max(RuleVersion.version_no)).filter(
            RuleVersion.rule_id == rule.id))).scalar() or 0
        self.db.add(RuleVersion(
            organization_id=rule.organization_id, rule_id=rule.id, version_no=last + 1,
            snapshot={"name": rule.name, "description": rule.description, "category": rule.category,
                      "entity_type": rule.entity_type, "definition": rule.definition,
                      "actions": rule.actions, "priority": rule.priority,
                      "conflict_strategy": rule.conflict_strategy},
            note=note, created_by=actor.id))
        await self.db.flush()

    async def list_versions(self, actor: User, rule_id: uuid.UUID) -> list[dict]:
        await self._get(actor, rule_id)  # ownership check
        rows = (await self.db.execute(select(RuleVersion).filter(
            RuleVersion.rule_id == rule_id, RuleVersion.organization_id == actor.organization_id,
            RuleVersion.is_deleted == False).order_by(RuleVersion.version_no.desc()))).scalars().all()
        return [{"id": str(v.id), "version_no": v.version_no, "note": v.note, "snapshot": v.snapshot,
                 "created_at": v.created_at.isoformat() if v.created_at else None} for v in rows]

    async def restore_version(self, actor: User, rule_id: uuid.UUID, version_no: int) -> dict:
        self._require_manager(actor)
        r = await self._get(actor, rule_id)
        v = (await self.db.execute(select(RuleVersion).filter(
            RuleVersion.rule_id == rule_id, RuleVersion.organization_id == actor.organization_id,
            RuleVersion.version_no == version_no, RuleVersion.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        await self._snapshot(actor, r, note=f"before restore to v{version_no}")
        snap = v.snapshot or {}
        for f in ("name", "description", "category", "entity_type", "definition", "actions",
                  "priority", "conflict_strategy"):
            if f in snap:
                setattr(r, f, snap[f])
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="RULE_RESTORED", resource_type="rule", resource_id=str(r.id),
                                   action_metadata={"version_no": version_no})
        return self._serialize(r)

    # ---------- actions ----------
    @staticmethod
    def _owner_id(entity, entity_type: str):
        if entity_type == "user":
            return getattr(entity, "id", None)
        for attr in ("assigned_user_id", "assigned_to_id", "requested_by", "user_id", "created_by"):
            v = getattr(entity, attr, None)
            if v:
                return v
        return None

    async def apply_actions(self, actor: User, rule: Rule, entity, entity_id=None) -> list[str]:
        """Run a matched rule's actions (notifications). Non-destructive and
        idempotent-safe to call per match."""
        done: list[str] = []
        owner_id = self._owner_id(entity, rule.entity_type)
        for action in (rule.actions or []):
            t = action.get("type")
            recipients: set = set()
            if t == "notify_owner" and owner_id:
                recipients.add(owner_id)
            elif t == "notify_user" and action.get("user_id"):
                recipients.add(uuid.UUID(str(action["user_id"])))
            elif t == "notify_manager":
                if owner_id:
                    mgr = (await self.db.execute(select(User.reporting_to_id).filter(
                        User.id == owner_id))).scalar()
                    if mgr:
                        recipients.add(mgr)
            elif t == "notify_role" and action.get("role"):
                rows = (await self.db.execute(select(User.id).filter(
                    User.organization_id == rule.organization_id, User.is_deleted == False,
                    User.role == action["role"]))).scalars().all()
                recipients.update(rows)
            msg = action.get("message") or f'Rule "{rule.name}" matched.'
            for rid in recipients:
                await self.notifier.create_notification(
                    organization_id=rule.organization_id, user_id=rid, category="rule",
                    title="Business rule triggered", body=msg, link_url="/rules",
                    action_metadata={"rule_id": str(rule.id), "entity_id": str(entity_id or getattr(entity, "id", "")) or None})
            if recipients:
                done.append(f"{t}→{len(recipients)}")
        return done

    # ---------- simulation (batch dry-run + optional action execution) ----------
    async def simulate(self, actor: User, rule_id: uuid.UUID, limit: int = 50, execute: bool = False) -> dict:
        """Run a rule against a batch of recent live entities of its type. With
        execute=False it's a pure dry run (Rule Simulation); execute=True also
        fires the matched rule's actions."""
        self._require_manager(actor)
        rule = await self._get(actor, rule_id)
        Model = self._model_for(rule.entity_type)
        if Model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Simulation against live {rule.entity_type} entities is not supported.")
        rows = (await self.db.execute(select(Model).filter(
            Model.organization_id == actor.organization_id, Model.is_deleted == False
        ).order_by(Model.created_at.desc()).limit(min(limit, 200)))).scalars().all()
        samples: list[dict] = []
        matched = executed = 0
        for obj in rows:
            res = await self.evaluate_rule(actor, rule, obj, log=False)
            if res["matched"]:
                matched += 1
                if execute:
                    ran = await self.apply_actions(actor, rule, obj)
                    if ran:
                        executed += 1
            if len(samples) < 20:
                samples.append({"entity_id": str(getattr(obj, "id", "")), "matched": res["matched"]})
        await self.db.flush()
        return {"rule_id": str(rule.id), "name": rule.name, "entity_type": rule.entity_type,
                "evaluated": len(rows), "matched": matched, "executed": executed,
                "action_count": len(rule.actions or []), "samples": samples}

    @staticmethod
    def _model_for(entity_type: str):
        import importlib
        path = {
            "lead": "app.models.lead.Lead", "contact": "app.models.contact.Contact",
            "task": "app.models.task.Task", "user": "app.models.user.User",
            "attendance": "app.models.attendance.AttendanceRecord",
            "leave": "app.models.leave.LeaveRequest",
        }.get(entity_type)
        if not path:
            return None
        mod, cls = path.rsplit(".", 1)
        return getattr(importlib.import_module(mod), cls)

    # ---------- audit log ----------
    async def audit_logs(self, actor: User, limit: int = 50) -> list[dict]:
        rows = (await self.db.execute(select(AuditLog).filter(
            AuditLog.organization_id == actor.organization_id,
            AuditLog.resource_type.in_(["rule", "rule_component"])
        ).order_by(AuditLog.created_at.desc()).limit(min(limit, 200)))).scalars().all()
        actor_ids = {a.actor_user_id for a in rows if a.actor_user_id}
        names = {}
        if actor_ids:
            res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(
                User.id.in_(actor_ids)))
            names = {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}
        return [{"id": str(a.id), "action": a.action, "resource_type": a.resource_type,
                 "resource_id": a.resource_id, "actor_name": names.get(a.actor_user_id),
                 "metadata": a.action_metadata,
                 "created_at": a.created_at.isoformat() if a.created_at else None} for a in rows]

    # ---------- serialize ----------
    def _serialize(self, r: Rule) -> dict:
        def _count(node) -> int:
            if isinstance(node, dict) and (node.get("type") == "group" or "children" in node):
                return sum(_count(c) for c in (node.get("children") or []))
            return 1
        return {"id": str(r.id), "organization_id": str(r.organization_id), "name": r.name,
                "description": r.description, "category": r.category, "entity_type": r.entity_type,
                "definition": r.definition, "actions": r.actions or [], "priority": r.priority,
                "conflict_strategy": r.conflict_strategy, "is_active": r.is_active,
                "is_template": r.is_template, "condition_count": _count(ev._normalize(r.definition)),
                "action_count": len(r.actions or []),
                "match_count": r.match_count, "eval_count": r.eval_count,
                "last_evaluated_at": r.last_evaluated_at.isoformat() if r.last_evaluated_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None}

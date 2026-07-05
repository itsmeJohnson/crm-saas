"""Bounded lead-automation engine.

Evaluates active WorkflowRule rows for a trigger event, checks their conditions
against a lead, and applies their actions. Intentionally NOT a general-purpose
engine: a fixed, safe set of fields/operators/action-types keeps evaluation
predictable and injection-free. Actions mutate the lead directly (never via the
lead update path) so a rule cannot recursively re-trigger itself.
"""
import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_rule import WorkflowRule
from app.models.lead import Lead
from app.models.user import User

CONDITION_FIELDS = {"status", "source", "priority", "value", "stage_id", "city", "company_name"}
ACTION_TYPES = {"set_priority", "set_status", "set_source", "assign_user", "add_note", "notify_user", "move_stage", "send_sms", "send_whatsapp", "send_email", "add_to_campaign", "assign_to_team", "assign_territory"}

# Contact-entity variants
CONTACT_CONDITION_FIELDS = {"job_title", "email", "phone", "company_id", "first_name", "last_name"}
CONTACT_ACTION_TYPES = {"assign_user", "add_note", "notify_user", "add_tag"}

# Task-entity variants
TASK_CONDITION_FIELDS = {"status", "priority", "assigned_user_id", "recurrence"}
TASK_ACTION_TYPES = {"set_status", "set_priority", "assign_user", "notify_user"}

# Attendance-entity variants (event-driven, read-only conditions on the record)
ATTENDANCE_CONDITION_FIELDS = {"status", "is_late", "late_minutes", "shift_id"}
ATTENDANCE_ACTION_TYPES = {"notify_user", "notify_manager", "add_note"}

# Leave-entity variants (event-driven; conditions on the request)
LEAVE_CONDITION_FIELDS = {"status", "request_type", "leave_type_id", "day_count", "is_half_day"}
LEAVE_ACTION_TYPES = {"notify_user", "notify_manager", "add_note"}

# Shift-entity variants (event-driven; fired on shift assignment)
SHIFT_CONDITION_FIELDS = {"shift_id"}
SHIFT_ACTION_TYPES = {"notify_user", "notify_manager"}

# Performance-entity variants (event-driven; fired when a goal is achieved)
PERFORMANCE_CONDITION_FIELDS = {"kpi_id", "attainment"}
PERFORMANCE_ACTION_TYPES = {"notify_user", "notify_manager"}

# Approval-entity variants (event-driven; fired on final decision)
APPROVAL_CONDITION_FIELDS = {"request_type", "amount", "status"}
APPROVAL_ACTION_TYPES = {"notify_user", "notify_manager"}

# Which field/action sets & entity apply per trigger
# call_logged fires when a Call activity is created against a lead (dialer,
# inbound webhook, or Communication Center); call_disposition fires when a
# telecaller submits a disposition. Both act on the linked lead.
_TRIGGER_ENTITY = {
    "lead_created": "lead", "lead_updated": "lead",
    "contact_created": "contact", "contact_updated": "contact",
    "task_created": "task", "task_updated": "task",
    "call_logged": "lead", "call_disposition": "lead",
    "sms_received": "lead", "whatsapp_received": "lead", "email_received": "lead",
    "attendance_marked": "attendance", "late_login": "attendance",
    "leave_applied": "leave", "leave_approved": "leave",
    "shift_assigned": "shift",
    "goal_achieved": "performance",
    "approval_approved": "approval", "approval_rejected": "approval",
}


def _fields_for(entity_type: str) -> set:
    if entity_type == "contact":
        return CONTACT_CONDITION_FIELDS
    if entity_type == "task":
        return TASK_CONDITION_FIELDS
    if entity_type == "attendance":
        return ATTENDANCE_CONDITION_FIELDS
    if entity_type == "leave":
        return LEAVE_CONDITION_FIELDS
    if entity_type == "shift":
        return SHIFT_CONDITION_FIELDS
    if entity_type == "performance":
        return PERFORMANCE_CONDITION_FIELDS
    if entity_type == "approval":
        return APPROVAL_CONDITION_FIELDS
    return CONDITION_FIELDS


def _actions_for(entity_type: str) -> set:
    if entity_type == "contact":
        return CONTACT_ACTION_TYPES
    if entity_type == "task":
        return TASK_ACTION_TYPES
    if entity_type == "attendance":
        return ATTENDANCE_ACTION_TYPES
    if entity_type == "leave":
        return LEAVE_ACTION_TYPES
    if entity_type == "shift":
        return SHIFT_ACTION_TYPES
    if entity_type == "performance":
        return PERFORMANCE_ACTION_TYPES
    if entity_type == "approval":
        return APPROVAL_ACTION_TYPES
    return ACTION_TYPES


def _coerce_number(v):
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _match_condition(entity, cond: dict, allowed_fields: set) -> bool:
    field = cond.get("field")
    op = cond.get("op")
    expected = cond.get("value")
    if field not in allowed_fields:
        return False
    actual = getattr(entity, field, None)
    if field in ("stage_id", "company_id") and actual is not None:
        actual = str(actual)

    if op in ("gt", "gte", "lt", "lte"):
        a, e = _coerce_number(actual), _coerce_number(expected)
        if a is None or e is None:
            return False
        return {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[op]
    if op == "eq":
        return str(actual) == str(expected)
    if op == "neq":
        return str(actual) != str(expected)
    if op == "contains":
        return expected is not None and actual is not None and str(expected).lower() in str(actual).lower()
    return False


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def matches(entity, conditions: list, entity_type: str = "lead") -> bool:
        """All conditions must hold (AND). Empty conditions => always matches."""
        allowed = _fields_for(entity_type)
        return all(_match_condition(entity, c, allowed) for c in (conditions or []))

    # --- CRUD ---
    VALID_TRIGGERS = {"lead_created", "lead_updated", "contact_created", "contact_updated", "task_created", "task_updated", "call_logged", "call_disposition", "sms_received", "whatsapp_received", "email_received", "attendance_marked", "late_login", "leave_applied", "leave_approved", "shift_assigned", "goal_achieved", "approval_approved", "approval_rejected"}

    def _validate_rule(self, conditions: list, actions: list, trigger_event: str) -> None:
        from fastapi import HTTPException, status
        if trigger_event not in self.VALID_TRIGGERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid trigger_event. Allowed: {sorted(self.VALID_TRIGGERS)}")
        entity_type = _TRIGGER_ENTITY.get(trigger_event, "lead")
        allowed_fields = _fields_for(entity_type)
        allowed_actions = _actions_for(entity_type)
        for c in (conditions or []):
            if c.get("field") not in allowed_fields:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid condition field for {entity_type}: {c.get('field')}")
        for a in (actions or []):
            if a.get("type") not in allowed_actions:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action type for {entity_type}: {a.get('type')}")

    async def list_rules(self, actor: User) -> list[WorkflowRule]:
        res = await self.db.execute(
            select(WorkflowRule).filter(
                WorkflowRule.organization_id == actor.organization_id,
                WorkflowRule.is_deleted == False,
            ).order_by(WorkflowRule.created_at.desc())
        )
        return list(res.scalars().all())

    async def create_rule(self, actor: User, data: dict) -> WorkflowRule:
        self._validate_rule(data.get("conditions"), data.get("actions"), data.get("trigger_event"))
        rule = WorkflowRule(
            organization_id=actor.organization_id,
            name=data["name"],
            trigger_event=data["trigger_event"],
            is_active=data.get("is_active", True),
            conditions=data.get("conditions", []),
            actions=data.get("actions", []),
            created_by=actor.id,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def _get_owned_rule(self, actor: User, rule_id: uuid.UUID) -> WorkflowRule:
        from fastapi import HTTPException, status
        res = await self.db.execute(
            select(WorkflowRule).filter(
                WorkflowRule.id == rule_id,
                WorkflowRule.organization_id == actor.organization_id,
                WorkflowRule.is_deleted == False,
            )
        )
        rule = res.scalars().first()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow rule not found")
        return rule

    async def update_rule(self, actor: User, rule_id: uuid.UUID, data: dict) -> WorkflowRule:
        rule = await self._get_owned_rule(actor, rule_id)
        merged_conditions = data.get("conditions", rule.conditions)
        merged_actions = data.get("actions", rule.actions)
        merged_trigger = data.get("trigger_event", rule.trigger_event)
        self._validate_rule(merged_conditions, merged_actions, merged_trigger)
        for key, val in data.items():
            setattr(rule, key, val)
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, actor: User, rule_id: uuid.UUID) -> None:
        rule = await self._get_owned_rule(actor, rule_id)
        rule.is_deleted = True
        self.db.add(rule)
        await self.db.flush()

    async def run(self, trigger_event: str, entity, actor: User, entity_type: str = "lead") -> list[str]:
        """Apply every active matching rule; return a list of applied action descriptions."""
        res = await self.db.execute(
            select(WorkflowRule).filter(
                WorkflowRule.organization_id == entity.organization_id,
                WorkflowRule.trigger_event == trigger_event,
                WorkflowRule.is_active == True,
                WorkflowRule.is_deleted == False,
            )
        )
        rules = res.scalars().all()
        applied: list[str] = []
        for rule in rules:
            if not self.matches(entity, rule.conditions, entity_type):
                continue
            rule_applied: list[str] = []
            for action in (rule.actions or []):
                if entity_type == "contact":
                    desc = await self._apply_contact_action(entity, action, actor, rule)
                elif entity_type == "task":
                    desc = await self._apply_task_action(entity, action, actor, rule)
                elif entity_type == "attendance":
                    desc = await self._apply_attendance_action(entity, action, actor, rule)
                elif entity_type == "leave":
                    desc = await self._apply_leave_action(entity, action, actor, rule)
                elif entity_type == "shift":
                    desc = await self._apply_shift_action(entity, action, actor, rule)
                elif entity_type == "performance":
                    desc = await self._apply_performance_action(entity, action, actor, rule)
                elif entity_type == "approval":
                    desc = await self._apply_approval_action(entity, action, actor, rule)
                else:
                    desc = await self._apply_action(entity, action, actor, rule)
                if desc:
                    rule_applied.append(desc)
            if rule_applied:
                applied.extend(rule_applied)
                # Audit each firing so it surfaces in timelines (workflow/automation events)
                from app.services.audit_service import AuditService
                await AuditService(self.db).log_event(
                    organization_id=entity.organization_id,
                    actor_user_id=getattr(actor, "id", None),
                    action="WORKFLOW_EXECUTED",
                    resource_type=entity_type,
                    resource_id=str(entity.id),
                    action_metadata={"rule": rule.name, "trigger": trigger_event, "actions": rule_applied},
                )
        if applied:
            # Persist mutated fields for real ORM entities. Some entity types
            # (e.g. the lightweight shift-assignment event) aren't mapped rows
            # and must not be added to the session.
            from app.models.base import Base as _Base
            if isinstance(entity, _Base):
                self.db.add(entity)
                await self.db.flush()
        return applied

    async def _apply_task_action(self, task, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        atype = action.get("type")
        if atype not in TASK_ACTION_TYPES:
            return None
        if atype == "set_status" and action.get("value"):
            task.status = str(action["value"])
            return f"set_status={task.status}"
        if atype == "set_priority" and action.get("value"):
            task.priority = str(action["value"])
            return f"set_priority={task.priority}"
        if atype == "assign_user" and action.get("user_id"):
            try:
                task.assigned_user_id = uuid.UUID(str(action["user_id"]))
                return "assign_user"
            except ValueError:
                return None
        if atype == "notify_user":
            from app.services.notification_service import NotificationService
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else task.assigned_user_id
            except ValueError:
                target_id = task.assigned_user_id
            if target_id:
                await NotificationService(self.db).create_notification(
                    organization_id=task.organization_id, user_id=target_id, category="task",
                    title=f"Workflow: {rule.name}",
                    body=str(action.get("message") or f'Rule "{rule.name}" fired for task "{task.title}".'),
                    link_url=f"/tasks?taskId={task.id}",
                    action_metadata={"task_id": str(task.id), "rule_id": str(rule.id)},
                )
                return "notify_user"
        return None

    async def _apply_attendance_action(self, record, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        """Attendance rules fire on clock-in (attendance_marked) and on a late
        arrival (late_login). Actions are notification/annotation only — the
        record is never mutated in a way that recomputes attendance."""
        atype = action.get("type")
        if atype not in ATTENDANCE_ACTION_TYPES:
            return None
        from app.services.notification_service import NotificationService
        if atype == "add_note":
            note = str(action.get("content") or action.get("message") or "").strip()
            if not note:
                return None
            record.notes = f"{record.notes}\n{note}" if record.notes else note
            return "add_note"
        if atype in ("notify_user", "notify_manager"):
            target_id = None
            if atype == "notify_manager":
                target_id = (await self.db.execute(
                    select(User.reporting_to_id).filter(User.id == record.user_id))).scalar()
            else:
                target = action.get("user_id")
                try:
                    target_id = uuid.UUID(str(target)) if target else record.user_id
                except ValueError:
                    target_id = record.user_id
            if target_id:
                await NotificationService(self.db).create_notification(
                    organization_id=record.organization_id, user_id=target_id, category="attendance",
                    title=f"Workflow: {rule.name}",
                    body=str(action.get("message") or f'Rule "{rule.name}" fired for attendance on {record.work_date}.'),
                    link_url="/attendance",
                    action_metadata={"attendance_id": str(record.id), "rule_id": str(rule.id)},
                )
                return atype
        return None

    async def _apply_leave_action(self, req, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        """Leave rules fire when a request is applied (leave_applied) or approved
        (leave_approved). Actions notify or annotate only."""
        atype = action.get("type")
        if atype not in LEAVE_ACTION_TYPES:
            return None
        from app.services.notification_service import NotificationService
        if atype == "add_note":
            note = str(action.get("content") or action.get("message") or "").strip()
            if not note:
                return None
            req.review_note = f"{req.review_note}\n{note}" if req.review_note else note
            return "add_note"
        if atype in ("notify_user", "notify_manager"):
            if atype == "notify_manager":
                target_id = (await self.db.execute(
                    select(User.reporting_to_id).filter(User.id == req.user_id))).scalar()
            else:
                target = action.get("user_id")
                try:
                    target_id = uuid.UUID(str(target)) if target else req.user_id
                except ValueError:
                    target_id = req.user_id
            if target_id:
                await NotificationService(self.db).create_notification(
                    organization_id=req.organization_id, user_id=target_id, category="leave",
                    title=f"Workflow: {rule.name}",
                    body=str(action.get("message") or f'Rule "{rule.name}" fired for a leave request ({req.start_date} → {req.end_date}).'),
                    link_url="/leaves",
                    action_metadata={"request_id": str(req.id), "rule_id": str(rule.id)},
                )
                return atype
        return None

    async def _apply_shift_action(self, event, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        """Shift rules fire when a shift (direct or rotation) is assigned to a
        user. `event` carries organization_id, user_id and shift_id."""
        atype = action.get("type")
        if atype not in SHIFT_ACTION_TYPES:
            return None
        from app.services.notification_service import NotificationService
        if atype == "notify_manager":
            target_id = (await self.db.execute(
                select(User.reporting_to_id).filter(User.id == event.user_id))).scalar()
        else:
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else event.user_id
            except ValueError:
                target_id = event.user_id
        if target_id:
            await NotificationService(self.db).create_notification(
                organization_id=event.organization_id, user_id=target_id, category="shift",
                title=f"Workflow: {rule.name}",
                body=str(action.get("message") or f'Rule "{rule.name}" fired on a shift assignment.'),
                link_url="/shifts", action_metadata={"user_id": str(event.user_id), "rule_id": str(rule.id)})
            return atype
        return None

    async def _apply_performance_action(self, event, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        """Performance rules fire when a user achieves a goal. `event` carries
        organization_id, user_id, kpi_id and attainment."""
        atype = action.get("type")
        if atype not in PERFORMANCE_ACTION_TYPES:
            return None
        from app.services.notification_service import NotificationService
        if atype == "notify_manager":
            target_id = (await self.db.execute(
                select(User.reporting_to_id).filter(User.id == event.user_id))).scalar()
        else:
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else event.user_id
            except ValueError:
                target_id = event.user_id
        if target_id:
            await NotificationService(self.db).create_notification(
                organization_id=event.organization_id, user_id=target_id, category="performance",
                title=f"Workflow: {rule.name}",
                body=str(action.get("message") or f'Rule "{rule.name}" fired on a performance goal.'),
                link_url="/performance", action_metadata={"user_id": str(event.user_id), "rule_id": str(rule.id)})
            return atype
        return None

    async def _apply_approval_action(self, event, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        """Approval rules fire on a final decision (approval_approved/rejected).
        `event` carries organization_id, id, user_id (requester), request_type,
        amount and status."""
        atype = action.get("type")
        if atype not in APPROVAL_ACTION_TYPES:
            return None
        from app.services.notification_service import NotificationService
        if atype == "notify_manager":
            target_id = (await self.db.execute(
                select(User.reporting_to_id).filter(User.id == event.user_id))).scalar()
        else:
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else event.user_id
            except ValueError:
                target_id = event.user_id
        if target_id:
            await NotificationService(self.db).create_notification(
                organization_id=event.organization_id, user_id=target_id, category="approval",
                title=f"Workflow: {rule.name}",
                body=str(action.get("message") or f'Rule "{rule.name}" fired on a {event.request_type} approval.'),
                link_url="/approvals", action_metadata={"request_id": str(event.id), "rule_id": str(rule.id)})
            return atype
        return None

    async def _apply_contact_action(self, contact, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        atype = action.get("type")
        if atype not in CONTACT_ACTION_TYPES:
            return None
        if atype == "add_tag" and action.get("value"):
            tags = list(contact.tags or [])
            tag = str(action["value"])
            if tag not in tags:
                tags.append(tag)
            contact.tags = tags
            return f"add_tag={tag}"
        if atype == "assign_user" and action.get("user_id"):
            try:
                contact.assigned_user_id = uuid.UUID(str(action["user_id"]))
                return "assign_user"
            except ValueError:
                return None
        if atype == "add_note" and action.get("content"):
            from app.models.note import Note
            self.db.add(Note(
                organization_id=contact.organization_id,
                content=str(action["content"]),
                contact_id=contact.id,
                created_by=actor.id,
            ))
            return "add_note"
        if atype == "notify_user":
            from app.services.notification_service import NotificationService
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else contact.assigned_user_id
            except ValueError:
                target_id = contact.assigned_user_id
            if target_id:
                await NotificationService(self.db).create_notification(
                    organization_id=contact.organization_id,
                    user_id=target_id,
                    category="contact",
                    title=f"Workflow: {rule.name}",
                    body=str(action.get("message") or f'Rule "{rule.name}" fired for {contact.first_name} {contact.last_name}.'),
                    link_url=f"/contacts?contactId={contact.id}",
                    action_metadata={"contact_id": str(contact.id), "rule_id": str(rule.id)},
                )
                return "notify_user"
        return None

    async def _apply_action(self, lead: Lead, action: dict, actor: User, rule: WorkflowRule) -> str | None:
        atype = action.get("type")
        if atype not in ACTION_TYPES:
            return None

        if atype == "set_priority" and action.get("value"):
            lead.priority = str(action["value"])
            return f"set_priority={lead.priority}"
        if atype == "set_status" and action.get("value"):
            lead.status = str(action["value"])
            return f"set_status={lead.status}"
        if atype == "set_source" and action.get("value"):
            lead.source = str(action["value"])
            return f"set_source={lead.source}"
        if atype == "assign_user" and action.get("user_id"):
            try:
                lead.assigned_user_id = uuid.UUID(str(action["user_id"]))
                return "assign_user"
            except ValueError:
                return None
        if atype == "move_stage" and action.get("stage_id"):
            from app.models.pipeline import PipelineStage
            try:
                stage_uuid = uuid.UUID(str(action["stage_id"]))
            except ValueError:
                return None
            st = await self.db.execute(
                select(PipelineStage.id).filter(
                    PipelineStage.id == stage_uuid,
                    PipelineStage.organization_id == lead.organization_id,
                    PipelineStage.is_deleted == False,
                )
            )
            if st.scalar():
                lead.stage_id = stage_uuid
                return "move_stage"
            return None
        if atype == "add_note" and action.get("content"):
            from app.models.note import Note
            self.db.add(Note(
                organization_id=lead.organization_id,
                content=str(action["content"]),
                lead_id=lead.id,
                created_by=actor.id,
            ))
            return "add_note"
        if atype == "notify_user":
            from app.services.notification_service import NotificationService
            target = action.get("user_id")
            try:
                target_id = uuid.UUID(str(target)) if target else lead.assigned_user_id
            except ValueError:
                target_id = lead.assigned_user_id
            if target_id:
                # Dispatch honours the recipient's per-category channel preferences
                # (in-app always; email/SMS/WhatsApp/push only if they opted in).
                await NotificationService(self.db).dispatch(
                    organization_id=lead.organization_id,
                    user_id=target_id,
                    category="lead",
                    title=f"Workflow: {rule.name}",
                    body=str(action.get("message") or f'Rule "{rule.name}" fired for lead "{lead.title}".'),
                    link_url=f"/leads?leadId={lead.id}",
                    action_metadata={"lead_id": str(lead.id), "rule_id": str(rule.id)},
                )
                return "notify_user"
        if atype == "send_sms" and action.get("message") and lead.phone:
            # Automated outbound SMS to the lead's phone via the org's provider.
            # Failures are swallowed so a provider outage can't break rule evaluation.
            from app.services.sms_service import SmsService
            try:
                await SmsService(self.db).send(actor, {
                    "body": str(action["message"]),
                    "to_number": lead.phone,
                    "lead_id": lead.id,
                }, _skip_cap=True)
                return "send_sms"
            except Exception:
                return None
        if atype == "send_whatsapp" and action.get("message") and lead.phone:
            # Automated WhatsApp reply to the lead. Best-effort: a closed 24h window
            # or provider outage raises, which we swallow so rule evaluation continues.
            from app.services.whatsapp_service import WhatsAppService
            try:
                await WhatsAppService(self.db).send_text(actor, {
                    "body": str(action["message"]),
                    "to_number": lead.phone,
                    "lead_id": lead.id,
                })
                return "send_whatsapp"
            except Exception:
                return None
        if atype == "send_email" and action.get("message") and lead.email:
            # Automated email to the lead. Best-effort; swallow transport errors.
            from app.services.email_service_module import EmailModuleService
            try:
                await EmailModuleService(self.db).send(actor, {
                    "subject": str(action.get("subject") or f'Regarding {lead.title}'),
                    "body": str(action["message"]),
                    "to": lead.email,
                    "lead_id": lead.id,
                })
                return "send_email"
            except Exception:
                return None
        if atype == "assign_to_team" and action.get("team_id"):
            # Distribute the lead to the least-loaded active member of a team.
            from app.models.team import Team
            from app.services.team_service import TeamService
            try:
                team_uuid = uuid.UUID(str(action["team_id"]))
            except ValueError:
                return None
            team = (await self.db.execute(select(Team).filter(
                Team.id == team_uuid, Team.organization_id == lead.organization_id,
                Team.is_deleted == False, Team.status == "active"))).scalars().first()
            if not team:
                return None
            svc = TeamService(self.db)
            member_ids = await svc._member_ids(team.id)
            if not member_ids:
                return None
            active = list((await self.db.execute(select(User.id).filter(
                User.id.in_(member_ids), User.is_active == True,
                User.is_deleted == False))).scalars().all())
            if not active:
                return None
            lead.assigned_user_id = await svc._pick_least_loaded(lead.organization_id, active)
            return "assign_to_team"
        if atype == "assign_territory":
            # Resolve the lead's branch+territory from its PIN/city mapping (or
            # apply an explicit territory_id/branch_id from the action).
            from app.services.branch_territory_service import BranchTerritoryService
            svc = BranchTerritoryService(self.db)
            tid = bid = None
            if action.get("territory_id"):
                try:
                    tid = uuid.UUID(str(action["territory_id"]))
                except ValueError:
                    tid = None
            if action.get("branch_id"):
                try:
                    bid = uuid.UUID(str(action["branch_id"]))
                except ValueError:
                    bid = None
            if tid is None and bid is None:
                resolved = await svc.resolve_for_lead(lead.organization_id, lead.pin_code, lead.city)
                if not resolved:
                    return None
                tid = resolved.get("territory_id")
                bid = resolved.get("branch_id")
            if tid:
                lead.territory_id = tid
            if bid:
                lead.branch_id = bid
            return "assign_territory" if (tid or bid) else None
        if atype == "add_to_campaign" and action.get("campaign_id"):
            # Enrol the lead into a campaign's recipient queue.
            from app.services.campaign_service import CampaignService
            try:
                cid = uuid.UUID(str(action["campaign_id"]))
            except ValueError:
                return None
            try:
                added = await CampaignService(self.db).add_lead(cid, lead)
                return "add_to_campaign" if added else None
            except Exception:
                return None
        return None

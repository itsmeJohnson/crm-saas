"""AI Workflow Assistant — data-driven workflow / automation / rule
suggestions, bottleneck detection, optimization hygiene, natural-language
workflow generation, validation lint, simulation and execution insights.

Composes the existing automation stack: WorkflowEngineService (graph engine,
test-mode, validation), WorkflowExecution(+Step) logs, QueueJob, SLABreach,
ApprovalRequest and CRM data. Suggestions and detections are deterministic and
evidence-backed (live counts, never guesses); the AI gateway is used only for
the optional human narrative — never a provider directly. NO new tables.
"""
import csv
import io
import re
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.task import Task
from app.models.workflow import Workflow, WorkflowExecution, WorkflowExecutionStep
from app.models.queue import QueueJob
from app.models.automation import SLABreach
from app.models.approval import ApprovalRequest
from app.services.audit_service import AuditService
from app.services.workflow_engine_service import WorkflowEngineService, TRIGGER_ENTITY

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
TERMINAL_LEAD_STATUSES = ("Converted", "Lost", "Closed", "Dead")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _rate(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def _graph(trigger_conditions: list | None, actions: list[dict]) -> dict:
    """Build a linear trigger → action₁ → … → end graph in the engine's shape."""
    nodes = [{"id": "t1", "type": "trigger",
              "config": {"conditions": trigger_conditions or []}}]
    edges = []
    prev = "t1"
    for i, cfg in enumerate(actions, 1):
        nid = f"a{i}"
        nodes.append({"id": nid, "type": "action", "config": cfg})
        edges.append({"from": prev, "to": nid})
        prev = nid
    nodes.append({"id": "end", "type": "end", "config": {}})
    edges.append({"from": prev, "to": "end"})
    return {"nodes": nodes, "edges": edges}


# ---------- natural-language parsing (Auto Workflow Generation) ----------
_TRIGGER_PATTERNS: list[tuple[str, str]] = [
    (r"lead\s+is\s+converted|converts?\b|conversion", "lead_converted"),
    (r"new\s+lead|lead\s+(?:is\s+)?(?:created|comes?\s+in|arrives)", "lead_created"),
    (r"lead\s+(?:is\s+)?(?:updated|changes)", "lead_updated"),
    (r"call\s+(?:is\s+)?(?:logged|made|completed)|after\s+a\s+call", "call_logged"),
    (r"task\s+(?:is\s+)?completed?|finishes?\s+a\s+task", "task_completed"),
    (r"task\s+(?:is\s+)?created", "task_created"),
    (r"payment\s+(?:is\s+)?received|customer\s+pays", "payment_received"),
    (r"invoice\s+(?:is\s+)?created|new\s+invoice", "invoice_created"),
    (r"sla\s+(?:is\s+)?breach", "sla_breached"),
    (r"email\s+(?:is\s+)?received|incoming\s+email", "email_received"),
    (r"whatsapp\s+(?:message\s+)?received", "whatsapp_received"),
    (r"sms\s+received", "sms_received"),
    (r"leave\s+(?:is\s+)?approved", "leave_approved"),
    (r"leave\s+(?:is\s+)?applied", "leave_applied"),
    (r"approval\s+(?:is\s+)?approved", "approval_approved"),
    (r"employee\s+(?:is\s+)?(?:created|joins)|new\s+user", "user_created"),
]

_STATUS_WORDS = ("new", "contacted", "qualified", "converted", "lost", "follow-up", "followup")


def parse_workflow_prompt(prompt: str) -> dict:
    """Deterministic NL → workflow draft: trigger, inline trigger conditions and
    a chain of action nodes. Returns {trigger_event, conditions, actions, notes}."""
    p = (prompt or "").lower()
    notes: list[str] = []

    trigger = None
    for rx, t in _TRIGGER_PATTERNS:
        if re.search(rx, p):
            trigger = t
            break
    if not trigger:
        trigger = "lead_created"
        notes.append("No explicit trigger found — defaulted to lead_created.")

    conditions: list[dict] = []
    m = re.search(r"(?:value|worth|deal)\s*(?:is\s*)?(?:over|above|greater\s+than|>|more\s+than)\s*(?:₹|rs\.?|inr|\$)?\s*([\d,]+)", p)
    if m:
        conditions.append({"field": "value", "op": "gt", "value": float(m.group(1).replace(",", ""))})
    elif re.search(r"high[\s-]value", p):
        conditions.append({"field": "value", "op": "gt", "value": 50000})
        notes.append("Interpreted 'high value' as value > 50,000 — adjust to taste.")
    m = re.search(r"source\s+(?:is|=|equals?)\s+['\"]?([a-z0-9 _-]{2,30}?)['\"]?(?:\s+(?:and|or|then|,)|$)", p)
    if m:
        conditions.append({"field": "source", "op": "eq", "value": m.group(1).strip().title()})
    m = re.search(r"status\s+(?:is|=|equals?|becomes)\s+['\"]?([a-z -]{2,20}?)['\"]?(?:\s+(?:and|or|then|,)|$)", p)
    if m and m.group(1).strip() in _STATUS_WORDS:
        conditions.append({"field": "status", "op": "eq", "value": m.group(1).strip().title()})
    m = re.search(r"priority\s+(?:is\s+)?(high|medium|low)", p)
    if m:
        conditions.append({"field": "priority", "op": "eq", "value": m.group(1).title()})

    actions: list[dict] = []
    # message-bearing actions are matched against the ORIGINAL prompt so a
    # quoted message keeps its capitalization
    m = re.search(r"(?:send|shoot)\s+(?:an?\s+)?email(?:\s+saying\s+['\"]?([^'\"]{3,120})['\"]?)?", prompt, re.IGNORECASE)
    if m:
        actions.append({"action": "send_email", "subject": "Automated follow-up",
                        "message": (m.group(1) or "Thanks for reaching out — we will get back to you shortly.").strip()})
    m = re.search(r"send\s+(?:an?\s+)?sms(?:\s+saying\s+['\"]?([^'\"]{3,120})['\"]?)?", prompt, re.IGNORECASE)
    if m:
        actions.append({"action": "send_sms",
                        "message": (m.group(1) or "Thanks! Our team will contact you soon.").strip()})
    m = re.search(r"(?:send\s+(?:a\s+)?whatsapp|whatsapp\s+(?:them|message))(?:\s+saying\s+['\"]?([^'\"]{3,120})['\"]?)?", prompt, re.IGNORECASE)
    if m:
        actions.append({"action": "send_whatsapp",
                        "message": (m.group(1) or "Hi! Thanks for your interest — talk soon.").strip()})
    m = re.search(r"create\s+(?:a\s+)?task(?:\s+(?:to|for)\s+([^,.]{3,80}))?", p)
    if m:
        actions.append({"action": "create_task",
                        "title": (m.group(1) or "Follow up").strip().capitalize()})
    if re.search(r"assign\b", p):
        actions.append({"action": "assign_lead" if TRIGGER_ENTITY.get(trigger) == "lead" else "assign_task"})
        notes.append("Assignment action added — pick the user in the workflow builder.")
    m = re.search(r"(?:update|change|set)\s+(?:the\s+)?status\s+to\s+['\"]?([a-z -]{2,20}?)['\"]?(?:\s|$|,|\.)", p)
    if m:
        actions.append({"action": "update_status", "value": m.group(1).strip().title()})
    if re.search(r"notify|notification|alert", p):
        actions.append({"action": "create_notification", "title": "Workflow alert",
                        "message": f"Triggered by {trigger.replace('_', ' ')}"})
    m = re.search(r"(?:schedule|book)\s+(?:a\s+)?meeting", p)
    if m:
        actions.append({"action": "schedule_meeting", "title": "Follow-up meeting"})
    m = re.search(r"webhook\s+(?:to\s+)?(https?://\S+)", p)
    if m:
        actions.append({"action": "webhook", "url": m.group(1).rstrip(".,")})

    if not actions:
        actions.append({"action": "create_notification", "title": "Workflow triggered",
                        "message": "Review this record."})
        notes.append("No explicit action found — added a notification as a safe default.")

    return {"trigger_event": trigger, "conditions": conditions, "actions": actions, "notes": notes}


class WorkflowAssistantService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.engine = WorkflowEngineService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    async def _org_workflows(self, org) -> list[Workflow]:
        return (await self.db.execute(select(Workflow).filter(
            Workflow.organization_id == org, Workflow.is_deleted == False,
            Workflow.is_template == False))).scalars().all()

    async def _executions(self, org, days: int = 30) -> list[WorkflowExecution]:
        cutoff = _now() - timedelta(days=days)
        rows = (await self.db.execute(select(WorkflowExecution).filter(
            WorkflowExecution.organization_id == org,
            WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False)
            .order_by(WorkflowExecution.started_at.desc()).limit(3000))).scalars().all()
        return [e for e in rows if e.started_at and _aware(e.started_at) >= cutoff]

    # ================= Workflow Suggestions =================
    async def suggestions(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        workflows = await self._org_workflows(org)
        covered = {w.trigger_event for w in workflows if w.status == "published" and w.is_enabled}
        now = _now()

        leads = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org, Lead.is_deleted == False))).scalars().all()
        open_leads = [l for l in leads if (l.status or "") not in TERMINAL_LEAD_STATUSES]
        unassigned = [l for l in open_leads if not l.assigned_user_id]
        stale = [l for l in open_leads if l.updated_at and (now - _aware(l.updated_at)).days >= 7]
        overdue_tasks = (await self.db.execute(select(func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False,
            Task.status.in_(("Todo", "InProgress")),
            Task.due_date != None))).scalar() or 0
        breaches = (await self.db.execute(select(func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False))).scalar() or 0

        out: list[dict] = []

        def add(key, title, reason, trigger, impact, graph, category="Sales"):
            out.append({"key": key, "title": title, "reason": reason, "impact": impact,
                        "trigger_event": trigger, "category": category,
                        "already_covered": trigger in covered, "draft_graph": graph})

        if unassigned:
            add("auto_assign_leads", "Auto-assign new leads",
                f"{len(unassigned)} open lead(s) currently have no owner — new leads are falling through.",
                "lead_created", "high",
                _graph(None, [{"action": "assign_lead"},
                              {"action": "create_notification", "title": "New lead assigned",
                               "message": "A new lead was auto-assigned to you."}]))
        if stale:
            add("stale_lead_followup", "Stale-lead follow-up nudge",
                f"{len(stale)} open lead(s) untouched for 7+ days — an automatic follow-up task keeps them moving.",
                "lead_updated", "high",
                _graph([{"field": "status", "op": "neq", "value": "Converted"}],
                       [{"action": "create_task", "title": "Follow up with stale lead"}]))
        if "lead_created" not in covered:
            add("welcome_new_lead", "Instant new-lead welcome",
                "No published workflow greets new leads today — an instant email/SMS raises contact rates.",
                "lead_created", "medium",
                _graph(None, [{"action": "send_email", "subject": "Thanks for reaching out",
                               "message": "We received your enquiry and will call you shortly."}]))
        if "lead_converted" not in covered:
            add("conversion_handoff", "Conversion → onboarding handoff",
                "Converted leads get no automated handoff — create the onboarding task automatically.",
                "lead_converted", "medium",
                _graph(None, [{"action": "create_task", "title": "Start customer onboarding"},
                              {"action": "create_notification", "title": "Lead converted",
                               "message": "A lead just converted — onboarding task created."}]),
                category="Onboarding")
        if overdue_tasks:
            add("task_deadline_guard", "Overdue-task alert",
                f"{overdue_tasks} open task(s) carry due dates — alert owners when tasks complete late or sit open.",
                "task_updated", "medium",
                _graph(None, [{"action": "create_notification", "title": "Task needs attention",
                               "message": "A task you own was updated — check its due date."}]),
                category="Operations")
        if breaches and "sla_breached" not in covered:
            add("sla_escalation", "SLA-breach escalation",
                f"{breaches} SLA breach(es) recorded but no workflow reacts to sla_breached.",
                "sla_breached", "high",
                _graph(None, [{"action": "create_notification", "title": "SLA breached",
                               "message": "An SLA just breached — please intervene."}]),
                category="Support")
        if "payment_received" not in covered:
            add("payment_thanks", "Payment received acknowledgement",
                "Payments arrive without an automated acknowledgement to the customer team.",
                "payment_received", "low",
                _graph(None, [{"action": "create_notification", "title": "Payment received",
                               "message": "A payment was recorded — send the receipt."}]),
                category="Finance")

        out.sort(key=lambda s: ({"high": 0, "medium": 1, "low": 2}[s["impact"]], s["already_covered"]))
        return {"suggestions": out, "count": len(out),
                "signals": {"open_leads": len(open_leads), "unassigned_leads": len(unassigned),
                            "stale_leads": len(stale), "overdue_open_tasks": int(overdue_tasks),
                            "sla_breaches": int(breaches),
                            "published_triggers": sorted(covered)}}

    # ================= Automation Suggestions =================
    async def automation_suggestions(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        out: list[dict] = []
        dead = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.status == "dead_letter"))).scalar() or 0
        failed = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.status == "failed"))).scalar() or 0
        if dead:
            out.append({"key": "dlq_review", "impact": "high",
                        "title": "Clear the dead-letter queue",
                        "reason": f"{dead} job(s) exhausted retries and sit in the DLQ — requeue or fix their handlers.",
                        "area": "queue"})
        if failed:
            out.append({"key": "retry_tuning", "impact": "medium",
                        "title": "Tune retry policy for failing jobs",
                        "reason": f"{failed} queue job(s) in failed state — consider higher max_attempts or backoff.",
                        "area": "queue"})
        from app.models.activity import Activity
        cutoff = _now() - timedelta(days=7)
        acts = (await self.db.execute(select(Activity).filter(
            Activity.organization_id == org, Activity.is_deleted == False)
            .order_by(Activity.created_at.desc()).limit(1000))).scalars().all()
        recent = [a for a in acts if a.created_at and _aware(a.created_at) >= cutoff]
        manual_msgs = [a for a in recent if a.activity_type in ("SMS", "Email", "WhatsApp")]
        if len(manual_msgs) >= 25:
            out.append({"key": "bulk_campaign", "impact": "medium",
                        "title": "Move repetitive messaging into a Campaign",
                        "reason": f"{len(manual_msgs)} individual SMS/Email/WhatsApp messages in 7 days — a segmented campaign automates this.",
                        "area": "campaigns"})
        wf_disabled = (await self.db.execute(select(func.count(Workflow.id)).filter(
            Workflow.organization_id == org, Workflow.is_deleted == False,
            Workflow.is_template == False, Workflow.status == "published",
            Workflow.is_enabled == False))).scalar() or 0
        if wf_disabled:
            out.append({"key": "enable_published", "impact": "low",
                        "title": "Re-enable published workflows",
                        "reason": f"{wf_disabled} published workflow(s) are switched off — they run nothing while disabled.",
                        "area": "workflows"})
        return {"suggestions": out, "count": len(out)}

    # ================= Rule Recommendations =================
    async def rule_recommendations(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        leads = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org, Lead.is_deleted == False))).scalars().all()
        out: list[dict] = []
        by_source: dict[str, list[Lead]] = {}
        for l in leads:
            by_source.setdefault(l.source or "Unknown", []).append(l)
        # top converting source → scoring rule
        best_src, best_rate = None, 0.0
        for src, ls in by_source.items():
            if len(ls) >= 5:
                r = _rate(sum(1 for l in ls if (l.status or "") == "Converted"), len(ls))
                if r > best_rate:
                    best_src, best_rate = src, r
        if best_src and best_rate >= 20:
            out.append({
                "key": "score_top_source", "impact": "high",
                "title": f"Boost scores for '{best_src}' leads",
                "reason": f"'{best_src}' converts at {best_rate}% — score these leads higher so reps call them first.",
                "rule_definition": {"type": "group", "logic": "AND", "children": [
                    {"field": "source", "op": "eq", "value": best_src}]},
                "suggested_action": "increase lead score / set priority High",
            })
        high_value_unassigned = [l for l in leads if (l.value or 0) > 50000 and not l.assigned_user_id
                                 and (l.status or "") not in TERMINAL_LEAD_STATUSES]
        if high_value_unassigned:
            out.append({
                "key": "assign_high_value", "impact": "high",
                "title": "Route high-value leads immediately",
                "reason": f"{len(high_value_unassigned)} unassigned lead(s) worth > ₹50k — an assignment rule removes the delay.",
                "rule_definition": {"type": "group", "logic": "AND", "children": [
                    {"field": "value", "op": "gt", "value": 50000},
                    {"field": "assigned_user_id", "op": "eq", "value": None}]},
                "suggested_action": "assign to senior rep / round-robin team",
            })
        no_phone = [l for l in leads if not (getattr(l, "phone", None) or getattr(l, "mobile", None))]
        if len(no_phone) >= 10:
            out.append({
                "key": "quality_gate", "impact": "medium",
                "title": "Flag incomplete leads at entry",
                "reason": f"{len(no_phone)} lead(s) have no phone number — a validation rule can flag them for enrichment.",
                "rule_definition": {"type": "group", "logic": "AND", "children": [
                    {"field": "phone", "op": "eq", "value": None}]},
                "suggested_action": "tag as needs-enrichment / notify owner",
            })
        return {"recommendations": out, "count": len(out)}

    # ================= Bottleneck Detection =================
    async def bottlenecks(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        now = _now()
        out: list[dict] = []

        execs = await self._executions(org)
        by_wf: dict[uuid.UUID, list[WorkflowExecution]] = {}
        for e in execs:
            by_wf.setdefault(e.workflow_id, []).append(e)
        wf_names = {w.id: w.name for w in await self._org_workflows(org)}
        for wid, es in by_wf.items():
            failed = [e for e in es if e.status == "failed"]
            fr = _rate(len(failed), len(es))
            if len(es) >= 5 and fr >= 25:
                out.append({"area": "workflow", "severity": "high",
                            "title": f"Workflow '{wf_names.get(wid, wid)}' fails often",
                            "evidence": f"{len(failed)}/{len(es)} runs failed ({fr}%) in 30 days. Last error: {failed[0].error or 'n/a'}",
                            "recommendation": "Inspect the failing node in execution logs; fix its config or add a condition guard."})
            durs = [( _aware(e.finished_at) - _aware(e.started_at)).total_seconds()
                    for e in es if e.finished_at]
            if durs and (sum(durs) / len(durs)) > 30:
                out.append({"area": "workflow", "severity": "medium",
                            "title": f"Workflow '{wf_names.get(wid, wid)}' is slow",
                            "evidence": f"Average run time {round(sum(durs)/len(durs), 1)}s over {len(durs)} runs.",
                            "recommendation": "Move heavy actions (webhooks, emails) to the background queue or split the workflow."})
        # failing steps by action type
        cutoff = now - timedelta(days=30)
        steps = (await self.db.execute(select(WorkflowExecutionStep).filter(
            WorkflowExecutionStep.organization_id == org,
            WorkflowExecutionStep.status == "failed")
            .order_by(WorkflowExecutionStep.created_at.desc()).limit(1000))).scalars().all()
        recent_failed_steps = [s for s in steps if s.created_at and _aware(s.created_at) >= cutoff]
        by_action: dict[str, int] = {}
        for s in recent_failed_steps:
            by_action[s.action_type or s.node_type] = by_action.get(s.action_type or s.node_type, 0) + 1
        for action_type, n in sorted(by_action.items(), key=lambda kv: kv[1], reverse=True)[:3]:
            if n >= 3:
                out.append({"area": "workflow-step", "severity": "medium",
                            "title": f"Action '{action_type}' keeps failing",
                            "evidence": f"{n} failed step(s) of this type across workflows in 30 days.",
                            "recommendation": "Check the integration this action depends on (mail/SMS settings, webhook endpoint)."})
        dead = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.status == "dead_letter"))).scalar() or 0
        if dead:
            out.append({"area": "queue", "severity": "high",
                        "title": "Jobs stuck in dead-letter queue",
                        "evidence": f"{dead} job(s) exhausted all retries.",
                        "recommendation": "Requeue after fixing the handler, or purge if obsolete."})
        pend = (await self.db.execute(select(ApprovalRequest).filter(
            ApprovalRequest.organization_id == org, ApprovalRequest.is_deleted == False,
            ApprovalRequest.status == "pending"))).scalars().all()
        old_pend = [a for a in pend if a.created_at and (now - _aware(a.created_at)).days >= 3]
        if old_pend:
            out.append({"area": "approvals", "severity": "medium",
                        "title": "Approvals sitting idle",
                        "evidence": f"{len(old_pend)} approval request(s) pending for 3+ days.",
                        "recommendation": "Add approval timeouts/auto-escalation in the Approval chains."})
        breaches = (await self.db.execute(select(SLABreach).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False))).scalars().all()
        recent_breaches = [b for b in breaches if b.created_at and _aware(b.created_at) >= cutoff]
        if recent_breaches:
            out.append({"area": "sla", "severity": "high",
                        "title": "SLA breaches this month",
                        "evidence": f"{len(recent_breaches)} breach(es) in 30 days.",
                        "recommendation": "Wire the sla_breached trigger to an escalation workflow."})
        leads = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org, Lead.is_deleted == False))).scalars().all()
        stuck = [l for l in leads if (l.status or "") not in TERMINAL_LEAD_STATUSES
                 and l.updated_at and (now - _aware(l.updated_at)).days >= 14]
        if stuck:
            out.append({"area": "pipeline", "severity": "medium",
                        "title": "Leads stuck in the pipeline",
                        "evidence": f"{len(stuck)} open lead(s) untouched for 14+ days.",
                        "recommendation": "Create the stale-lead follow-up workflow from Suggestions."})
        sev_rank = {"high": 0, "medium": 1, "low": 2}
        out.sort(key=lambda b: sev_rank[b["severity"]])
        return {"bottlenecks": out, "count": len(out),
                "areas": sorted({b["area"] for b in out})}

    # ================= Optimization Suggestions =================
    async def optimizations(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        now = _now()
        workflows = await self._org_workflows(org)
        execs = await self._executions(org)
        ran_ids = {e.workflow_id for e in execs}
        out: list[dict] = []
        for w in workflows:
            if w.status == "published" and not w.is_enabled:
                out.append({"workflow_id": str(w.id), "workflow": w.name, "kind": "disabled_published",
                            "advice": "Published but disabled — enable it or archive it."})
            elif w.status == "published" and w.id not in ran_ids:
                out.append({"workflow_id": str(w.id), "workflow": w.name, "kind": "never_ran",
                            "advice": "Published 30+ days of silence — its trigger may never fire; check the trigger/conditions."})
            elif w.status == "draft" and w.created_at and (now - _aware(w.created_at)).days >= 14:
                out.append({"workflow_id": str(w.id), "workflow": w.name, "kind": "stale_draft",
                            "advice": "Draft for 14+ days — publish it or delete it."})
            actions = [n for n in (w.graph or {}).get("nodes", []) if n.get("type") == "action"]
            if w.status == "published" and not actions:
                out.append({"workflow_id": str(w.id), "workflow": w.name, "kind": "no_actions",
                            "advice": "Published workflow has no action nodes — it does nothing."})
        by_trigger: dict[str, int] = {}
        for w in workflows:
            if w.status == "published" and w.is_enabled:
                by_trigger[w.trigger_event] = by_trigger.get(w.trigger_event, 0) + 1
        for t, n in by_trigger.items():
            if n >= 3:
                out.append({"workflow_id": None, "workflow": None, "kind": "trigger_crowding",
                            "advice": f"{n} enabled workflows all fire on '{t}' — consider merging them to keep ordering predictable."})
        return {"optimizations": out, "count": len(out)}

    # ================= Auto Workflow Generation =================
    async def generate(self, actor: User, prompt: str, *, create: bool = False,
                       name: str | None = None) -> dict:
        self._require_manager(actor)
        parsed = parse_workflow_prompt(prompt)
        graph = _graph(parsed["conditions"], parsed["actions"])
        # engine-level validation (raises 400 on an invalid draft)
        self.engine._validate_graph(parsed["trigger_event"], graph)
        wf_name = (name or f"Generated: {prompt.strip()[:60]}").strip()
        explanation = [
            f"Trigger: {parsed['trigger_event']} ({TRIGGER_ENTITY[parsed['trigger_event']]})",
            *(f"Condition: {c['field']} {c['op']} {c['value']}" for c in parsed["conditions"]),
            *(f"Action: {a['action']}" for a in parsed["actions"]),
            *parsed["notes"],
        ]
        created = None
        if create:
            created = await self.engine.create(actor, {
                "name": wf_name, "description": f"Auto-generated from: {prompt.strip()[:300]}",
                "category": "General", "trigger_event": parsed["trigger_event"],
                "graph": graph, "is_enabled": False})
            await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                       action="WORKFLOW_GENERATED", resource_type="workflow_assistant",
                                       resource_id=created["id"],
                                       action_metadata={"prompt": prompt[:300], "name": wf_name})
            await self.db.commit()
        return {"prompt": prompt, "name": wf_name, "trigger_event": parsed["trigger_event"],
                "entity_type": TRIGGER_ENTITY[parsed["trigger_event"]],
                "graph": graph, "explanation": explanation, "notes": parsed["notes"],
                "created": created, "status": "draft (disabled)" if created else "preview"}

    # ================= Validation lint =================
    async def validate(self, actor: User, workflow_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        w = await self.engine._get(actor, workflow_id)
        errors: list[str] = []
        warnings: list[str] = []
        graph = w.graph or {}
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        try:
            self.engine._validate_graph(w.trigger_event, graph)
        except HTTPException as e:
            errors.append(str(e.detail))
        node_ids = {n.get("id") for n in nodes}
        trigger_ids = [n.get("id") for n in nodes if n.get("type") == "trigger"]
        # reachability from the trigger
        if trigger_ids:
            reachable = set(trigger_ids)
            frontier = list(trigger_ids)
            adj: dict[str, list[str]] = {}
            for e in edges:
                adj.setdefault(e.get("from"), []).append(e.get("to"))
            while frontier:
                cur = frontier.pop()
                for nxt in adj.get(cur, []):
                    if nxt not in reachable:
                        reachable.add(nxt)
                        frontier.append(nxt)
            orphans = node_ids - reachable
            if orphans:
                warnings.append(f"Unreachable node(s): {sorted(orphans)} — no path from the trigger.")
        actions = [n for n in nodes if n.get("type") == "action"]
        if not actions:
            warnings.append("No action nodes — this workflow does nothing when it fires.")
        for n in actions:
            cfg = n.get("config") or {}
            a = cfg.get("action")
            if a in ("send_email", "send_sms", "send_whatsapp") and not cfg.get("message"):
                warnings.append(f"Node {n.get('id')}: '{a}' has no message configured.")
            if a in ("assign_lead", "assign_task") and not cfg.get("user_id"):
                warnings.append(f"Node {n.get('id')}: '{a}' has no target user — it will be skipped at runtime.")
            if a == "update_status" and not cfg.get("value"):
                warnings.append(f"Node {n.get('id')}: 'update_status' has no value.")
            if a == "webhook" and not cfg.get("url"):
                warnings.append(f"Node {n.get('id')}: 'webhook' has no URL.")
        if w.status != "published":
            warnings.append("Workflow is not published — it will not run on live events.")
        elif not w.is_enabled:
            warnings.append("Workflow is published but disabled.")
        execs = [e for e in await self._executions(actor.organization_id)
                 if e.workflow_id == w.id]
        if w.status == "published" and w.is_enabled and not execs:
            warnings.append("No executions in the last 30 days — the trigger may never fire.")
        score = max(0, 100 - 40 * len(errors) - 10 * len(warnings))
        return {"workflow_id": str(w.id), "name": w.name, "valid": not errors,
                "errors": errors, "warnings": warnings, "health_score": score,
                "runs_30d": len(execs)}

    # ================= Simulation (delegates to engine test-mode) =================
    async def simulate(self, actor: User, workflow_id: uuid.UUID) -> dict:
        return await self.engine.test_run(actor, workflow_id)

    # ================= Execution Insights =================
    async def insights(self, actor: User, workflow_id: uuid.UUID | None = None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        execs = await self._executions(org)
        if workflow_id:
            execs = [e for e in execs if e.workflow_id == workflow_id]
        wf_names = {w.id: w.name for w in await self._org_workflows(org)}
        per: dict[uuid.UUID, dict] = {}
        for e in execs:
            d = per.setdefault(e.workflow_id, {"runs": 0, "failed": 0, "durs": [], "last": None})
            d["runs"] += 1
            d["failed"] += 1 if e.status == "failed" else 0
            if e.finished_at:
                d["durs"].append((_aware(e.finished_at) - _aware(e.started_at)).total_seconds())
            la = _aware(e.started_at)
            if d["last"] is None or la > d["last"]:
                d["last"] = la
        rows = []
        for wid, d in per.items():
            rows.append({"workflow_id": str(wid), "workflow": wf_names.get(wid, "deleted"),
                         "runs_30d": d["runs"], "failed": d["failed"],
                         "success_rate": _rate(d["runs"] - d["failed"], d["runs"]),
                         "avg_duration_s": round(sum(d["durs"]) / len(d["durs"]), 2) if d["durs"] else None,
                         "last_run": d["last"].isoformat() if d["last"] else None})
        rows.sort(key=lambda r: r["runs_30d"], reverse=True)
        by_day: dict[str, dict] = {}
        for e in execs:
            k = _aware(e.started_at).date().isoformat()
            b = by_day.setdefault(k, {"runs": 0, "failed": 0})
            b["runs"] += 1
            b["failed"] += 1 if e.status == "failed" else 0
        trend = [{"day": k, **v} for k, v in sorted(by_day.items())][-14:]
        total, failed = len(execs), sum(1 for e in execs if e.status == "failed")
        return {"window_days": 30, "totals": {"runs": total, "failed": failed,
                                              "success_rate": _rate(total - failed, total)},
                "workflows": rows, "trend": trend}

    # ================= Report / export =================
    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        sugg = await self.suggestions(actor)
        auto = await self.automation_suggestions(actor)
        rules = await self.rule_recommendations(actor)
        bott = await self.bottlenecks(actor)
        opt = await self.optimizations(actor)
        ins = await self.insights(actor)
        return {"generated_at": _now().isoformat(),
                "summary": {"workflow_suggestions": sugg["count"],
                            "automation_suggestions": auto["count"],
                            "rule_recommendations": rules["count"],
                            "bottlenecks": bott["count"],
                            "optimizations": opt["count"],
                            "runs_30d": ins["totals"]["runs"],
                            "success_rate": ins["totals"]["success_rate"]},
                "suggestions": sugg["suggestions"], "automation": auto["suggestions"],
                "rules": rules["recommendations"], "bottlenecks": bott["bottlenecks"],
                "optimizations": opt["optimizations"], "insights": ins}

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        rep = await self.report(actor)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["section", "title", "severity_or_impact", "detail"])
        for s in rep["suggestions"]:
            w.writerow(["workflow_suggestion", s["title"], s["impact"], s["reason"]])
        for s in rep["automation"]:
            w.writerow(["automation_suggestion", s["title"], s["impact"], s["reason"]])
        for r in rep["rules"]:
            w.writerow(["rule_recommendation", r["title"], r["impact"], r["reason"]])
        for b in rep["bottlenecks"]:
            w.writerow(["bottleneck", b["title"], b["severity"], b["evidence"]])
        for o in rep["optimizations"]:
            w.writerow(["optimization", o["workflow"] or "-", o["kind"], o["advice"]])
        for i in rep["insights"]["workflows"]:
            w.writerow(["insight", i["workflow"], f"{i['success_rate']}%",
                        f"{i['runs_30d']} runs, avg {i['avg_duration_s']}s"])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="WORKFLOW_ASSISTANT_EXPORTED", resource_type="workflow_assistant",
                                   action_metadata={"sections": 6})
        await self.db.commit()
        return buf.getvalue()

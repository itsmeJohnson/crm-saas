"""Automation Analytics — a unifying analytics layer over the whole automation
stack (workflow engine, background queue, rule engine, SLA, escalation, approval,
automation jobs).

Each subsystem already exposes its own dashboard/report; this aggregates them
into one date-filterable surface with the cross-cutting metrics: workflow success
rate / failures / execution time, queue statistics, rule usage, top automations,
SLA compliance, escalation & approval metrics, and time-bucketed trends. No new
tables — everything is computed from the existing execution/run logs.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workflow import Workflow, WorkflowExecution
from app.models.queue import QueueJob
from app.models.rule import Rule, RuleEvaluation
from app.models.automation import AutomationJob, AutomationRun, SLABreach
from app.models.sla import SLATracker
from app.models.escalation import EscalationEvent
from app.models.approval import ApprovalRequest

GRANULARITIES = ("daily", "weekly", "monthly")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class AutomationAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / window ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Automation analytics are available to managers and admins only.")

    def _window(self, date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
        today = date.today()
        to_d = date_to or today
        from_d = date_from or (to_d - timedelta(days=29))
        start = datetime.combine(from_d, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(to_d, time.max).replace(tzinfo=timezone.utc)
        return start, end

    @staticmethod
    def _rate(part: int, whole: int) -> float:
        return round(part * 100 / whole, 1) if whole else 0.0

    # ---------- per-subsystem blocks ----------
    async def _workflow_block(self, org, start, end) -> dict:
        rows = (await self.db.execute(select(WorkflowExecution.status, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False, WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end).group_by(WorkflowExecution.status))).all()
        by_status = {s: n for s, n in rows}
        runs = sum(by_status.values())
        completed = by_status.get("completed", 0)
        failed = by_status.get("failed", 0)
        # average execution time (completed executions with both timestamps)
        pairs = (await self.db.execute(select(WorkflowExecution.started_at, WorkflowExecution.finished_at).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False, WorkflowExecution.status == "completed",
            WorkflowExecution.finished_at.isnot(None), WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end))).all()
        durs = [max(0.0, (_aware(f) - _aware(s)).total_seconds() * 1000) for s, f in pairs if s and f]
        avg_ms = round(sum(durs) / len(durs), 1) if durs else 0.0
        max_ms = round(max(durs), 1) if durs else 0.0
        return {"total_runs": runs, "completed": completed, "failed": failed,
                "paused": by_status.get("paused", 0), "success_rate": self._rate(completed, runs),
                "failure_rate": self._rate(failed, runs), "avg_execution_ms": avg_ms, "max_execution_ms": max_ms}

    async def _queue_block(self, org, start, end) -> dict:
        rows = (await self.db.execute(select(QueueJob.status, func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.created_at >= start, QueueJob.created_at <= end).group_by(QueueJob.status))).all()
        by_status = {s: n for s, n in rows}
        total = sum(by_status.values())
        succeeded = by_status.get("succeeded", 0)
        avg_ms = (await self.db.execute(select(func.avg(QueueJob.duration_ms)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False, QueueJob.duration_ms.isnot(None),
            QueueJob.created_at >= start, QueueJob.created_at <= end))).scalar()
        return {"total": total, "succeeded": succeeded, "failed": by_status.get("failed", 0),
                "dead_letter": by_status.get("dead_letter", 0), "queued": by_status.get("queued", 0),
                "running": by_status.get("running", 0), "success_rate": self._rate(succeeded, total),
                "avg_duration_ms": round(float(avg_ms), 1) if avg_ms is not None else 0.0}

    async def _automation_jobs_block(self, org, start, end) -> dict:
        rows = (await self.db.execute(select(AutomationRun.status, func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False,
            AutomationRun.started_at >= start, AutomationRun.started_at <= end).group_by(AutomationRun.status))).all()
        by_status = {s: n for s, n in rows}
        total = sum(by_status.values())
        success = by_status.get("success", 0)
        items = (await self.db.execute(select(func.sum(AutomationRun.items_processed)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False,
            AutomationRun.started_at >= start, AutomationRun.started_at <= end))).scalar() or 0
        avg_ms = (await self.db.execute(select(func.avg(AutomationRun.duration_ms)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False, AutomationRun.duration_ms.isnot(None),
            AutomationRun.started_at >= start, AutomationRun.started_at <= end))).scalar()
        enabled_jobs = (await self.db.execute(select(func.count(AutomationJob.id)).filter(
            AutomationJob.organization_id == org, AutomationJob.is_deleted == False,
            AutomationJob.is_enabled == True))).scalar() or 0
        return {"runs": total, "success": success, "failed": by_status.get("failed", 0),
                "partial": by_status.get("partial", 0), "success_rate": self._rate(success, total),
                "items_processed": int(items), "avg_duration_ms": round(float(avg_ms), 1) if avg_ms is not None else 0.0,
                "enabled_jobs": enabled_jobs}

    async def _rules_block(self, org, start, end) -> dict:
        total = (await self.db.execute(select(func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(Rule.id)).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False,
            Rule.is_active == True))).scalar() or 0
        evals = (await self.db.execute(select(func.count(RuleEvaluation.id)).filter(
            RuleEvaluation.organization_id == org, RuleEvaluation.is_deleted == False,
            RuleEvaluation.created_at >= start, RuleEvaluation.created_at <= end))).scalar() or 0
        matches = (await self.db.execute(select(func.count(RuleEvaluation.id)).filter(
            RuleEvaluation.organization_id == org, RuleEvaluation.is_deleted == False,
            RuleEvaluation.matched == True, RuleEvaluation.created_at >= start,
            RuleEvaluation.created_at <= end))).scalar() or 0
        return {"total": total, "active": active, "evaluations": evals, "matches": matches,
                "match_rate": self._rate(matches, evals)}

    async def _sla_block(self, org, start, end) -> dict:
        rows = (await self.db.execute(select(SLATracker.status, func.count(SLATracker.id)).filter(
            SLATracker.organization_id == org, SLATracker.is_deleted == False,
            SLATracker.started_at >= start, SLATracker.started_at <= end).group_by(SLATracker.status))).all()
        by_status = {s: n for s, n in rows}
        total = sum(by_status.values())
        breached = by_status.get("breached", 0)
        met = by_status.get("met", 0) + by_status.get("response_met", 0)
        open_breaches = (await self.db.execute(select(func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False, SLABreach.resolved == False))).scalar() or 0
        # compliance = closed trackers that were met vs (met + breached)
        closed = met + breached
        return {"tracked": total, "breached": breached, "met": met, "open_breaches": open_breaches,
                "compliance_rate": self._rate(met, closed)}

    async def _escalation_block(self, org, start, end) -> dict:
        total = (await self.db.execute(select(func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False,
            EscalationEvent.escalated_at >= start, EscalationEvent.escalated_at <= end))).scalar() or 0
        by_level = {int(lvl): n for lvl, n in (await self.db.execute(select(
            EscalationEvent.level, func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False,
            EscalationEvent.escalated_at >= start, EscalationEvent.escalated_at <= end)
            .group_by(EscalationEvent.level))).all()}
        by_entity = {e: n for e, n in (await self.db.execute(select(
            EscalationEvent.entity_type, func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False,
            EscalationEvent.escalated_at >= start, EscalationEvent.escalated_at <= end)
            .group_by(EscalationEvent.entity_type))).all()}
        # serialize level 1-based for display
        return {"total": total, "by_level": {str(k + 1): v for k, v in sorted(by_level.items())},
                "by_entity": by_entity}

    async def _approval_block(self, org, start, end) -> dict:
        rows = (await self.db.execute(select(ApprovalRequest.status, func.count(ApprovalRequest.id)).filter(
            ApprovalRequest.organization_id == org, ApprovalRequest.is_deleted == False,
            ApprovalRequest.created_at >= start, ApprovalRequest.created_at <= end).group_by(ApprovalRequest.status))).all()
        by_status = {s: n for s, n in rows}
        total = sum(by_status.values())
        approved = by_status.get("approved", 0)
        rejected = by_status.get("rejected", 0)
        decided = approved + rejected
        # average decision time
        pairs = (await self.db.execute(select(ApprovalRequest.created_at, ApprovalRequest.decided_at).filter(
            ApprovalRequest.organization_id == org, ApprovalRequest.is_deleted == False,
            ApprovalRequest.decided_at.isnot(None), ApprovalRequest.created_at >= start,
            ApprovalRequest.created_at <= end))).all()
        hrs = [(_aware(dc) - _aware(cr)).total_seconds() / 3600 for cr, dc in pairs if cr and dc]
        return {"total": total, "approved": approved, "rejected": rejected,
                "pending": by_status.get("pending", 0), "cancelled": by_status.get("cancelled", 0),
                "approval_rate": self._rate(approved, decided),
                "avg_decision_hours": round(sum(hrs) / len(hrs), 1) if hrs else 0.0}

    # ---------- public surface ----------
    async def overview(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        return {
            "from": start.date().isoformat(), "to": end.date().isoformat(),
            "workflow": await self._workflow_block(org, start, end),
            "queue": await self._queue_block(org, start, end),
            "automation_jobs": await self._automation_jobs_block(org, start, end),
            "rules": await self._rules_block(org, start, end),
            "sla": await self._sla_block(org, start, end),
            "escalation": await self._escalation_block(org, start, end),
            "approval": await self._approval_block(org, start, end),
        }

    async def workflows(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        block = await self._workflow_block(org, start, end)
        # top workflows by run volume
        top = (await self.db.execute(select(WorkflowExecution.workflow_id, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False, WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end).group_by(WorkflowExecution.workflow_id)
            .order_by(func.count(WorkflowExecution.id).desc()).limit(10))).all()
        fail_by_wf = {wid: n for wid, n in (await self.db.execute(select(
            WorkflowExecution.workflow_id, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False, WorkflowExecution.status == "failed",
            WorkflowExecution.started_at >= start, WorkflowExecution.started_at <= end)
            .group_by(WorkflowExecution.workflow_id))).all()}
        names = {w.id: w.name for w in (await self.db.execute(select(Workflow).filter(
            Workflow.organization_id == org))).scalars().all()}
        top_workflows = [{"workflow_id": str(wid), "name": names.get(wid, "?"), "runs": n,
                          "failed": fail_by_wf.get(wid, 0)} for wid, n in top]
        # recent failures
        fails = (await self.db.execute(select(WorkflowExecution).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.status == "failed", WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end).order_by(WorkflowExecution.started_at.desc()).limit(15))).scalars().all()
        failures = [{"id": str(f.id), "workflow_id": str(f.workflow_id), "name": names.get(f.workflow_id, "?"),
                     "trigger_event": f.trigger_event, "error": f.error,
                     "started_at": f.started_at.isoformat() if f.started_at else None} for f in fails]
        return {**block, "top_workflows": top_workflows, "failures": failures}

    async def queue(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        block = await self._queue_block(org, start, end)
        by_queue = [{"queue": q, "count": n} for q, n in (await self.db.execute(select(
            QueueJob.queue, func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.created_at >= start, QueueJob.created_at <= end).group_by(QueueJob.queue)
            .order_by(func.count(QueueJob.id).desc()))).all()]
        by_type = [{"job_type": t, "count": n} for t, n in (await self.db.execute(select(
            QueueJob.job_type, func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.created_at >= start, QueueJob.created_at <= end).group_by(QueueJob.job_type)
            .order_by(func.count(QueueJob.id).desc()).limit(10))).all()]
        return {**block, "by_queue": by_queue, "by_type": by_type}

    async def rule_usage(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        block = await self._rules_block(org, start, end)
        top = (await self.db.execute(select(Rule).filter(
            Rule.organization_id == org, Rule.is_deleted == False, Rule.is_template == False)
            .order_by(Rule.eval_count.desc(), Rule.match_count.desc()).limit(10))).scalars().all()
        top_rules = [{"id": str(r.id), "name": r.name, "entity_type": r.entity_type,
                      "evaluations": r.eval_count, "matches": r.match_count,
                      "match_rate": self._rate(r.match_count, r.eval_count)} for r in top]
        return {**block, "top_rules": top_rules}

    async def top_automations(self, actor: User, date_from=None, date_to=None, limit: int = 10) -> dict:
        """A unified ranking of the busiest automations across workflows and jobs."""
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        wf = (await self.db.execute(select(WorkflowExecution.workflow_id, func.count(WorkflowExecution.id)).filter(
            WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
            WorkflowExecution.is_test == False, WorkflowExecution.started_at >= start,
            WorkflowExecution.started_at <= end).group_by(WorkflowExecution.workflow_id))).all()
        names = {w.id: w.name for w in (await self.db.execute(select(Workflow).filter(
            Workflow.organization_id == org))).scalars().all()}
        jobs = (await self.db.execute(select(AutomationRun.job_key, func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False,
            AutomationRun.started_at >= start, AutomationRun.started_at <= end).group_by(AutomationRun.job_key))).all()
        items = ([{"kind": "workflow", "name": names.get(wid, "?"), "runs": n} for wid, n in wf]
                 + [{"kind": "job", "name": k, "runs": n} for k, n in jobs])
        items.sort(key=lambda x: -x["runs"])
        return {"items": items[:limit]}

    async def sla_compliance(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date_from, date_to)
        block = await self._sla_block(org, start, end)
        by_metric = {m: n for m, n in (await self.db.execute(select(
            SLABreach.metric, func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False,
            SLABreach.breached_at >= start, SLABreach.breached_at <= end).group_by(SLABreach.metric))).all()}
        by_entity = {e: n for e, n in (await self.db.execute(select(
            SLABreach.entity_type, func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False,
            SLABreach.breached_at >= start, SLABreach.breached_at <= end).group_by(SLABreach.entity_type))).all()}
        return {**block, "breaches_by_metric": by_metric, "breaches_by_entity": by_entity}

    async def escalation_metrics(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        block = await self._escalation_block(actor.organization_id, start, end)
        by_target = {t: n for t, n in (await self.db.execute(select(
            EscalationEvent.escalate_to, func.count(EscalationEvent.id)).filter(
            EscalationEvent.organization_id == actor.organization_id, EscalationEvent.is_deleted == False,
            EscalationEvent.escalated_at >= start, EscalationEvent.escalated_at <= end)
            .group_by(EscalationEvent.escalate_to))).all() if t}
        return {**block, "by_target": by_target}

    async def approval_metrics(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        block = await self._approval_block(actor.organization_id, start, end)
        by_type = {t: n for t, n in (await self.db.execute(select(
            ApprovalRequest.request_type, func.count(ApprovalRequest.id)).filter(
            ApprovalRequest.organization_id == actor.organization_id, ApprovalRequest.is_deleted == False,
            ApprovalRequest.created_at >= start, ApprovalRequest.created_at <= end)
            .group_by(ApprovalRequest.request_type))).all()}
        return {**block, "by_type": by_type}

    async def trend(self, actor: User, granularity: str = "daily", date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        if granularity not in GRANULARITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"granularity must be one of {list(GRANULARITIES)}")
        org = actor.organization_id
        start, end = self._window(date_from, date_to)

        def bucket_key(dt: datetime) -> str:
            d = _aware(dt).date()
            if granularity == "daily":
                return d.isoformat()
            if granularity == "weekly":
                monday = d - timedelta(days=d.weekday())
                return monday.isoformat()
            return d.replace(day=1).isoformat()

        buckets: dict[str, dict] = {}

        def add(key: str, field: str, n: int = 1):
            b = buckets.setdefault(key, {"workflow_runs": 0, "workflow_failures": 0,
                                         "queue_jobs": 0, "automation_runs": 0, "escalations": 0, "approvals": 0})
            b[field] += n

        for s, st in (await self.db.execute(select(WorkflowExecution.started_at, WorkflowExecution.status).filter(
                WorkflowExecution.organization_id == org, WorkflowExecution.is_deleted == False,
                WorkflowExecution.is_test == False, WorkflowExecution.started_at >= start,
                WorkflowExecution.started_at <= end))).all():
            add(bucket_key(s), "workflow_runs")
            if st == "failed":
                add(bucket_key(s), "workflow_failures")
        for (c,) in (await self.db.execute(select(QueueJob.created_at).filter(
                QueueJob.organization_id == org, QueueJob.is_deleted == False,
                QueueJob.created_at >= start, QueueJob.created_at <= end))).all():
            add(bucket_key(c), "queue_jobs")
        for (s,) in (await self.db.execute(select(AutomationRun.started_at).filter(
                AutomationRun.organization_id == org, AutomationRun.is_deleted == False,
                AutomationRun.started_at >= start, AutomationRun.started_at <= end))).all():
            add(bucket_key(s), "automation_runs")
        for (e,) in (await self.db.execute(select(EscalationEvent.escalated_at).filter(
                EscalationEvent.organization_id == org, EscalationEvent.is_deleted == False,
                EscalationEvent.escalated_at >= start, EscalationEvent.escalated_at <= end))).all():
            add(bucket_key(e), "escalations")
        for (c,) in (await self.db.execute(select(ApprovalRequest.created_at).filter(
                ApprovalRequest.organization_id == org, ApprovalRequest.is_deleted == False,
                ApprovalRequest.created_at >= start, ApprovalRequest.created_at <= end))).all():
            add(bucket_key(c), "approvals")

        series = [{"bucket": k, **v} for k, v in sorted(buckets.items())]
        return {"granularity": granularity, "from": start.date().isoformat(),
                "to": end.date().isoformat(), "series": series}

    async def dashboard(self, actor: User) -> dict:
        """Compact figures for the Home widget (trailing 7 days)."""
        self._require_manager(actor)
        org = actor.organization_id
        start, end = self._window(date.today() - timedelta(days=6), date.today())
        wf = await self._workflow_block(org, start, end)
        q = await self._queue_block(org, start, end)
        sla = await self._sla_block(org, start, end)
        esc = await self._escalation_block(org, start, end)
        appr = await self._approval_block(org, start, end)
        return {"workflow_runs": wf["total_runs"], "workflow_success_rate": wf["success_rate"],
                "workflow_failed": wf["failed"], "queue_failed": q["failed"] + q["dead_letter"],
                "sla_compliance_rate": sla["compliance_rate"], "open_breaches": sla["open_breaches"],
                "escalations": esc["total"], "approvals_pending": appr["pending"]}

    async def export_csv(self, actor: User, date_from=None, date_to=None) -> str:
        self._require_manager(actor)
        ov = await self.overview(actor, date_from, date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Automation analytics", f"{ov['from']} → {ov['to']}"])
        w.writerow([])
        w.writerow(["Subsystem", "Metric", "Value"])
        flat = [
            ("Workflow", "Total runs", ov["workflow"]["total_runs"]),
            ("Workflow", "Success rate %", ov["workflow"]["success_rate"]),
            ("Workflow", "Failed", ov["workflow"]["failed"]),
            ("Workflow", "Avg execution ms", ov["workflow"]["avg_execution_ms"]),
            ("Queue", "Total", ov["queue"]["total"]),
            ("Queue", "Success rate %", ov["queue"]["success_rate"]),
            ("Queue", "Failed", ov["queue"]["failed"]),
            ("Queue", "Dead letter", ov["queue"]["dead_letter"]),
            ("Automation jobs", "Runs", ov["automation_jobs"]["runs"]),
            ("Automation jobs", "Success rate %", ov["automation_jobs"]["success_rate"]),
            ("Automation jobs", "Items processed", ov["automation_jobs"]["items_processed"]),
            ("Rules", "Evaluations", ov["rules"]["evaluations"]),
            ("Rules", "Match rate %", ov["rules"]["match_rate"]),
            ("SLA", "Tracked", ov["sla"]["tracked"]),
            ("SLA", "Compliance rate %", ov["sla"]["compliance_rate"]),
            ("SLA", "Open breaches", ov["sla"]["open_breaches"]),
            ("Escalation", "Events", ov["escalation"]["total"]),
            ("Approval", "Total", ov["approval"]["total"]),
            ("Approval", "Approval rate %", ov["approval"]["approval_rate"]),
            ("Approval", "Avg decision hours", ov["approval"]["avg_decision_hours"]),
        ]
        for row in flat:
            w.writerow(row)
        return buf.getvalue()

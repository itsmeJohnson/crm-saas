"""Automation Engine service.

The unifying orchestration + observability + policy layer over the CRM's
background automation. It does NOT re-implement the existing crons (lead
reminders, escalation, dunning, sms retry, email sync, campaigns) — it registers
them, runs them through a tracked runner (execution logs + retry + failure
handling), and adds the two genuinely-missing capabilities: SLA policies with
breach detection, and Scheduled Reports.

Design: each automation is a `job_key` in JOB_CATALOG. `run_tracked` executes a
job body, records an AutomationRun, retries on failure up to max_retries, and
rolls the outcome up onto the AutomationJob health counters. The same path is
used by manual "run now" (API) and the scheduled cycle (automation_cron).
"""
from __future__ import annotations
import uuid
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.automation import (
    AutomationJob, AutomationRun, SLAPolicy, SLABreach, ScheduledReport,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services import rule_evaluator as ev

# The registry of automation jobs. Runners are resolved in _run_body by job_key.
JOB_CATALOG = [
    {"job_key": "lead_reminders", "name": "Lead follow-up reminders", "category": "followup",
     "description": "Dispatch due lead follow-up reminders.", "schedule": "daily"},
    {"job_key": "task_reminders", "name": "Task reminders", "category": "followup",
     "description": "Notify assignees of due tasks.", "schedule": "daily"},
    {"job_key": "escalation", "name": "Idle-lead escalation", "category": "escalation",
     "description": "Escalate idle leads to the owner's manager.", "schedule": "daily"},
    {"job_key": "sla_scan", "name": "SLA breach scan", "category": "sla",
     "description": "Detect first-response / resolution SLA breaches.", "schedule": "hourly"},
    {"job_key": "scheduled_reports", "name": "Scheduled reports", "category": "reports",
     "description": "Generate and deliver recurring reports.", "schedule": "daily"},
    {"job_key": "dunning", "name": "Invoice dunning", "category": "finance",
     "description": "Chase overdue customer invoices.", "schedule": "daily"},
    {"job_key": "missed_call", "name": "Missed-call detection", "category": "communication",
     "description": "Flag and follow up missed calls.", "schedule": "daily"},
    {"job_key": "sms_retry", "name": "SMS retry", "category": "communication",
     "description": "Retry failed outbound SMS.", "schedule": "daily"},
    {"job_key": "email_sync", "name": "Email inbox sync", "category": "communication",
     "description": "Pull new inbound email.", "schedule": "daily"},
    {"job_key": "campaign", "name": "Campaign scheduler", "category": "campaign",
     "description": "Launch scheduled campaigns and sync engagement.", "schedule": "daily"},
]
JOB_KEYS = tuple(j["job_key"] for j in JOB_CATALOG)
JOB_META = {j["job_key"]: j for j in JOB_CATALOG}

SLA_METRICS = ("first_response", "resolution")
SLA_BREACH_ACTIONS = ("notify_owner", "notify_manager", "escalate")
REPORT_TYPES = ("lead_summary", "activity_summary", "sla_compliance", "automation_health")
FREQUENCIES = ("hourly", "daily", "weekly", "monthly")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes for TIMESTAMPTZ — coerce to UTC-aware."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _advance(base: datetime, frequency: str) -> datetime:
    return base + {"hourly": timedelta(hours=1), "daily": timedelta(days=1),
                   "weekly": timedelta(days=7), "monthly": timedelta(days=30)}.get(frequency, timedelta(days=1))


# ======================= tracked runner (module-level, shared) =======================
async def _run_body(db: AsyncSession, job_key: str, org_id: uuid.UUID) -> int:
    """Execute the actual work for a job_key against `db`; return items processed.
    Delegates to the existing cron scan functions (reusing, not reimplementing)."""
    if job_key == "lead_reminders":
        from app.cron.lead_cron import dispatch_due_reminders
        return await dispatch_due_reminders(db)
    if job_key == "task_reminders":
        from app.cron.lead_cron import dispatch_task_reminders
        return await dispatch_task_reminders(db)
    if job_key == "escalation":
        from app.cron.lead_cron import run_escalation_scan
        return await run_escalation_scan(db)
    if job_key == "sla_scan":
        return await AutomationService(db).run_sla_scan(org_id)
    if job_key == "scheduled_reports":
        return await AutomationService(db).run_scheduled_reports(org_id)
    # External crons manage their own sessions; run them best-effort (items=0).
    from app.core.database import async_session_maker
    if job_key == "dunning":
        from app.cron.customer_cron import run_customer_dunning_check
        await run_customer_dunning_check(async_session_maker)
    elif job_key == "missed_call":
        from app.cron.calling_cron import run_missed_call_check
        await run_missed_call_check(async_session_maker)
    elif job_key == "sms_retry":
        from app.cron.sms_cron import run_sms_retry_check
        await run_sms_retry_check(async_session_maker)
    elif job_key == "email_sync":
        from app.cron.email_cron import run_email_sync
        await run_email_sync(async_session_maker)
    elif job_key == "campaign":
        from app.cron.campaign_cron import run_campaign_check
        await run_campaign_check(async_session_maker)
    else:
        raise ValueError(f"Unknown job_key: {job_key}")
    return 0


async def run_tracked(db: AsyncSession, org_id: uuid.UUID, job_key: str, *,
                      triggered_by: str = "schedule", actor_user_id: uuid.UUID | None = None,
                      max_retries: int | None = None, job: AutomationJob | None = None) -> AutomationRun:
    """Run a job with execution logging, retry and failure handling. Records an
    AutomationRun and updates the job's health counters."""
    if job is None:
        job = await AutomationService(db)._ensure_job(org_id, job_key)
    retries = job.max_retries if max_retries is None else max_retries
    run = AutomationRun(organization_id=org_id, job_id=job.id, job_key=job_key, status="running",
                        triggered_by=triggered_by, actor_user_id=actor_user_id, started_at=_now())
    db.add(run)
    await db.flush()

    started = time.monotonic()
    items, error, attempt = 0, None, 0
    for attempt in range(retries + 1):
        try:
            items = await _run_body(db, job_key, org_id)
            error = None
            break
        except Exception as e:  # failure handling: capture, retry, or fail
            error = f"{type(e).__name__}: {e}"

    run.finished_at = _now()
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.items_processed = items or 0
    run.retry_count = attempt
    run.status = "failed" if error else "success"
    run.error = error
    db.add(run)

    job.last_run_at = run.finished_at
    job.last_status = run.status
    job.run_count = (job.run_count or 0) + 1
    if error:
        job.fail_count = (job.fail_count or 0) + 1
    job.next_run_at = _advance(_now(), job.schedule if job.schedule in FREQUENCIES else "daily")
    db.add(job)
    await db.flush()
    return run


class AutomationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage automation.")

    @staticmethod
    def catalog() -> dict:
        return {
            "jobs": JOB_CATALOG,
            "sla_metrics": list(SLA_METRICS),
            "sla_breach_actions": list(SLA_BREACH_ACTIONS),
            "report_types": list(REPORT_TYPES),
            "frequencies": list(FREQUENCIES),
        }

    # ======================= job registry =======================
    async def _ensure_job(self, org_id: uuid.UUID, job_key: str) -> AutomationJob:
        job = (await self.db.execute(select(AutomationJob).filter(
            AutomationJob.organization_id == org_id, AutomationJob.job_key == job_key,
            AutomationJob.is_deleted == False))).scalars().first()
        if job:
            return job
        meta = JOB_META.get(job_key, {"name": job_key, "category": "general", "schedule": "daily", "description": None})
        job = AutomationJob(organization_id=org_id, job_key=job_key, name=meta["name"],
                            category=meta["category"], description=meta.get("description"),
                            schedule=meta.get("schedule", "daily"), is_enabled=True, max_retries=1)
        self.db.add(job)
        await self.db.flush()
        return job

    async def sync_jobs(self, actor: User) -> list[dict]:
        """Bootstrap the catalog jobs for the org (idempotent) and return them."""
        for meta in JOB_CATALOG:
            await self._ensure_job(actor.organization_id, meta["job_key"])
        return await self.list_jobs(actor)

    async def list_jobs(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(AutomationJob).filter(
            AutomationJob.organization_id == actor.organization_id, AutomationJob.is_deleted == False
        ).order_by(AutomationJob.category, AutomationJob.name))).scalars().all()
        existing = {r.job_key for r in rows}
        # surface not-yet-bootstrapped catalog entries as virtual (enabled) rows
        out = [self._job_dict(r) for r in rows]
        for meta in JOB_CATALOG:
            if meta["job_key"] not in existing:
                out.append({"id": None, "job_key": meta["job_key"], "name": meta["name"],
                            "category": meta["category"], "description": meta.get("description"),
                            "is_enabled": True, "schedule": meta.get("schedule", "daily"), "max_retries": 1,
                            "last_run_at": None, "last_status": None, "next_run_at": None,
                            "run_count": 0, "fail_count": 0})
        out.sort(key=lambda d: (d["category"], d["name"]))
        return out

    async def set_job_enabled(self, actor: User, job_key: str, enabled: bool) -> dict:
        self._require_manager(actor)
        if job_key not in JOB_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown job.")
        job = await self._ensure_job(actor.organization_id, job_key)
        job.is_enabled = enabled
        self.db.add(job)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="AUTOMATION_JOB_TOGGLED", resource_type="automation_job",
                                   resource_id=str(job.id), action_metadata={"job_key": job_key, "enabled": enabled})
        return self._job_dict(job)

    async def set_job_config(self, actor: User, job_key: str, max_retries: int | None, schedule: str | None) -> dict:
        self._require_manager(actor)
        if job_key not in JOB_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown job.")
        job = await self._ensure_job(actor.organization_id, job_key)
        if max_retries is not None:
            job.max_retries = max(0, min(int(max_retries), 5))
        if schedule is not None:
            if schedule not in FREQUENCIES and schedule != "manual":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid schedule.")
            job.schedule = schedule
        self.db.add(job)
        await self.db.flush()
        return self._job_dict(job)

    async def run_job(self, actor: User, job_key: str, triggered_by: str = "manual") -> dict:
        """Manual 'run now'."""
        self._require_manager(actor)
        if job_key not in JOB_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown job.")
        job = await self._ensure_job(actor.organization_id, job_key)
        run = await run_tracked(self.db, actor.organization_id, job_key,
                                triggered_by=triggered_by, actor_user_id=actor.id, job=job)
        return self._run_dict(run)

    async def retry_run(self, actor: User, run_id: uuid.UUID) -> dict:
        """Re-run a previously failed run's job."""
        self._require_manager(actor)
        prev = (await self.db.execute(select(AutomationRun).filter(
            AutomationRun.id == run_id, AutomationRun.organization_id == actor.organization_id))).scalars().first()
        if not prev:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        job = await self._ensure_job(actor.organization_id, prev.job_key)
        run = await run_tracked(self.db, actor.organization_id, prev.job_key,
                                triggered_by="retry", actor_user_id=actor.id, job=job)
        return self._run_dict(run)

    # ======================= SLA policies =======================
    def _validate_sla(self, data: dict):
        if data.get("metric") and data["metric"] not in SLA_METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {SLA_METRICS}")
        if data.get("on_breach") and data["on_breach"] not in SLA_BREACH_ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"on_breach must be one of {SLA_BREACH_ACTIONS}")

    async def list_sla(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.organization_id == actor.organization_id, SLAPolicy.is_deleted == False
        ).order_by(SLAPolicy.created_at.desc()))).scalars().all()
        return [self._sla_dict(r) for r in rows]

    async def create_sla(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate_sla(data)
        p = SLAPolicy(organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
                      entity_type=data.get("entity_type") or "lead", metric=data.get("metric") or "first_response",
                      threshold_hours=float(data.get("threshold_hours", 24.0)), conditions=data.get("conditions"),
                      on_breach=data.get("on_breach") or "notify_manager", is_active=bool(data.get("is_active", True)),
                      created_by=actor.id)
        self.db.add(p)
        await self.db.flush()
        return self._sla_dict(p)

    async def update_sla(self, actor: User, policy_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        self._validate_sla(data)
        p = await self._get_sla(actor, policy_id)
        for f in ("name", "description", "entity_type", "metric", "threshold_hours", "conditions", "on_breach", "is_active"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        self.db.add(p)
        await self.db.flush()
        return self._sla_dict(p)

    async def delete_sla(self, actor: User, policy_id: uuid.UUID) -> None:
        self._require_manager(actor)
        p = await self._get_sla(actor, policy_id)
        p.is_deleted = True
        self.db.add(p)
        await self.db.flush()

    async def _get_sla(self, actor: User, policy_id: uuid.UUID) -> SLAPolicy:
        p = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.id == policy_id, SLAPolicy.organization_id == actor.organization_id,
            SLAPolicy.is_deleted == False))).scalars().first()
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA policy not found.")
        return p

    async def run_sla_scan(self, org_id: uuid.UUID) -> int:
        """Detect first-response / resolution breaches for a single org.
        Idempotent per (policy, entity) via an open SLABreach guard."""
        policies = (await self.db.execute(select(SLAPolicy).filter(
            SLAPolicy.organization_id == org_id, SLAPolicy.is_active == True,
            SLAPolicy.is_deleted == False, SLAPolicy.entity_type == "lead"))).scalars().all()
        if not policies:
            return 0
        now = _now()
        # first-activity time per lead for this org
        first_act = dict((lid, _aware(ts)) for lid, ts in (await self.db.execute(
            select(Activity.lead_id, func.min(Activity.created_at)).filter(
                Activity.organization_id == org_id, Activity.lead_id.isnot(None)
            ).group_by(Activity.lead_id))).all())
        leads = (await self.db.execute(select(Lead).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False, Lead.is_archived == False))).scalars().all()
        breaches = 0
        for policy in policies:
            thresh = timedelta(hours=policy.threshold_hours)
            for lead in leads:
                created = _aware(lead.created_at) or now
                # metric elapsed + breach test
                if policy.metric == "first_response":
                    ft = first_act.get(lead.id)
                    elapsed = (ft - created) if ft else (now - created)
                    breached = elapsed > thresh
                else:  # resolution
                    done = _aware(getattr(lead, "converted_at", None))
                    elapsed = (done - created) if done else (now - created)
                    breached = (done is None and elapsed > thresh) or (done is not None and elapsed > thresh)
                if not breached:
                    continue
                # optional condition gate (reuse the Rule Engine)
                if policy.conditions and not ev.evaluate(policy.conditions, self._lead_facts(lead), {"now": now}):
                    continue
                # dedup: already an open breach for this (policy, lead)?
                exists = (await self.db.execute(select(SLABreach.id).filter(
                    SLABreach.policy_id == policy.id, SLABreach.entity_id == lead.id,
                    SLABreach.resolved == False, SLABreach.is_deleted == False))).scalars().first()
                if exists:
                    continue
                b = SLABreach(organization_id=org_id, policy_id=policy.id, entity_type="lead",
                              entity_id=lead.id, metric=policy.metric,
                              hours_elapsed=round(elapsed.total_seconds() / 3600, 2), breached_at=now)
                self.db.add(b)
                policy.breach_count = (policy.breach_count or 0) + 1
                self.db.add(policy)
                await self._notify_breach(org_id, policy, lead, b)
                b.notified = True
                breaches += 1
        await self.db.flush()
        return breaches

    async def _notify_breach(self, org_id, policy: SLAPolicy, lead: Lead, breach: SLABreach):
        targets: set[uuid.UUID] = set()
        owner_id = lead.assigned_user_id
        if policy.on_breach == "notify_owner" and owner_id:
            targets.add(owner_id)
        elif policy.on_breach in ("notify_manager", "escalate"):
            if owner_id:
                mgr = (await self.db.execute(select(User.reporting_to_id).filter(User.id == owner_id))).scalar()
                if mgr:
                    targets.add(mgr)
                if policy.on_breach == "escalate" and owner_id:
                    targets.add(owner_id)
        for uid in targets:
            await self.notifier.create_notification(
                organization_id=org_id, user_id=uid, category="lead", priority="high",
                title=f"SLA breach: {policy.name}",
                body=f'Lead "{lead.title}" breached the {policy.metric.replace("_", " ")} SLA '
                     f'({breach.hours_elapsed}h ≥ {policy.threshold_hours}h).',
                link_url=f"/leads?leadId={lead.id}",
                action_metadata={"lead_id": str(lead.id), "policy_id": str(policy.id)})
        await self.audit.log_event(organization_id=org_id, actor_user_id=None, action="SLA_BREACH",
                                   resource_type="lead", resource_id=str(lead.id),
                                   action_metadata={"policy": policy.name, "metric": policy.metric,
                                                    "hours": breach.hours_elapsed})

    @staticmethod
    def _lead_facts(lead: Lead) -> dict:
        f = {}
        for k in ("status", "source", "priority", "value", "score", "city", "company_name"):
            v = getattr(lead, k, None)
            f[k] = str(v) if isinstance(v, uuid.UUID) else v
        return f

    async def list_breaches(self, actor: User, resolved: bool | None = None, limit: int = 50) -> list[dict]:
        q = select(SLABreach).filter(SLABreach.organization_id == actor.organization_id, SLABreach.is_deleted == False)
        if resolved is not None:
            q = q.filter(SLABreach.resolved == resolved)
        q = q.order_by(SLABreach.breached_at.desc()).limit(min(limit, 200))
        rows = (await self.db.execute(q)).scalars().all()
        return [self._breach_dict(b) for b in rows]

    async def resolve_breach(self, actor: User, breach_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        b = (await self.db.execute(select(SLABreach).filter(
            SLABreach.id == breach_id, SLABreach.organization_id == actor.organization_id))).scalars().first()
        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breach not found.")
        b.resolved = True
        self.db.add(b)
        await self.db.flush()
        return self._breach_dict(b)

    # ======================= scheduled reports =======================
    async def list_reports(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(ScheduledReport).filter(
            ScheduledReport.organization_id == actor.organization_id, ScheduledReport.is_deleted == False
        ).order_by(ScheduledReport.created_at.desc()))).scalars().all()
        return [self._report_dict(r) for r in rows]

    async def create_report(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        if data.get("report_type") and data["report_type"] not in REPORT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"report_type must be one of {REPORT_TYPES}")
        if data.get("frequency") and data["frequency"] not in FREQUENCIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"frequency must be one of {FREQUENCIES}")
        r = ScheduledReport(organization_id=actor.organization_id, name=data["name"],
                            report_type=data.get("report_type") or "lead_summary",
                            frequency=data.get("frequency") or "weekly", channel=data.get("channel") or "in_app",
                            recipients=[str(x) for x in (data.get("recipients") or [])],
                            is_active=bool(data.get("is_active", True)),
                            next_run_at=_advance(_now(), data.get("frequency") or "weekly"), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        return self._report_dict(r)

    async def update_report(self, actor: User, report_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        r = await self._get_report(actor, report_id)
        if "recipients" in data and data["recipients"] is not None:
            r.recipients = [str(x) for x in data["recipients"]]
        for f in ("name", "report_type", "frequency", "channel", "is_active"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        self.db.add(r)
        await self.db.flush()
        return self._report_dict(r)

    async def delete_report(self, actor: User, report_id: uuid.UUID) -> None:
        self._require_manager(actor)
        r = await self._get_report(actor, report_id)
        r.is_deleted = True
        self.db.add(r)
        await self.db.flush()

    async def _get_report(self, actor: User, report_id: uuid.UUID) -> ScheduledReport:
        r = (await self.db.execute(select(ScheduledReport).filter(
            ScheduledReport.id == report_id, ScheduledReport.organization_id == actor.organization_id,
            ScheduledReport.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled report not found.")
        return r

    async def run_report_now(self, actor: User, report_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        r = await self._get_report(actor, report_id)
        delivered = await self._deliver_report(r)
        await self.db.flush()
        return {"report_id": str(r.id), "delivered": delivered}

    async def run_scheduled_reports(self, org_id: uuid.UUID) -> int:
        """Deliver every active report that is due for a single org."""
        now = _now()
        reports = (await self.db.execute(select(ScheduledReport).filter(
            ScheduledReport.organization_id == org_id, ScheduledReport.is_active == True,
            ScheduledReport.is_deleted == False))).scalars().all()
        delivered = 0
        for r in reports:
            nxt = _aware(r.next_run_at)
            if nxt is not None and nxt > now:
                continue
            delivered += await self._deliver_report(r)
        await self.db.flush()
        return delivered

    async def _deliver_report(self, r: ScheduledReport) -> int:
        payload = await self._generate_report(r.organization_id, r.report_type)
        recipients = [uuid.UUID(x) for x in (r.recipients or []) if _is_uuid(x)]
        if not recipients:  # default to the creator
            recipients = [r.created_by]
        for uid in recipients:
            await self.notifier.create_notification(
                organization_id=r.organization_id, user_id=uid, category="report",
                title=f"Scheduled report: {r.name}", body=payload["summary"],
                link_url="/automation", action_metadata={"report_id": str(r.id), "data": payload["data"]})
        r.last_sent_at = _now()
        r.next_run_at = _advance(_now(), r.frequency)
        r.send_count = (r.send_count or 0) + 1
        self.db.add(r)
        return len(recipients)

    async def _generate_report(self, org_id: uuid.UUID, report_type: str) -> dict:
        now = _now()
        window = now - timedelta(days=7)
        if report_type == "lead_summary":
            total = (await self.db.execute(select(func.count(Lead.id)).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False))).scalar() or 0
            new = (await self.db.execute(select(func.count(Lead.id)).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False, Lead.created_at >= window))).scalar() or 0
            return {"summary": f"Lead summary: {total} total leads, {new} created in the last 7 days.",
                    "data": {"total": total, "new_7d": new}}
        if report_type == "activity_summary":
            acts = (await self.db.execute(select(func.count(Activity.id)).filter(
                Activity.organization_id == org_id, Activity.created_at >= window))).scalar() or 0
            return {"summary": f"Activity summary: {acts} activities logged in the last 7 days.",
                    "data": {"activities_7d": acts}}
        if report_type == "sla_compliance":
            breaches = (await self.db.execute(select(func.count(SLABreach.id)).filter(
                SLABreach.organization_id == org_id, SLABreach.is_deleted == False,
                SLABreach.breached_at >= window))).scalar() or 0
            return {"summary": f"SLA compliance: {breaches} breaches recorded in the last 7 days.",
                    "data": {"breaches_7d": breaches}}
        # automation_health
        runs = (await self.db.execute(select(func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org_id, AutomationRun.started_at >= window))).scalar() or 0
        failed = (await self.db.execute(select(func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org_id, AutomationRun.started_at >= window,
            AutomationRun.status == "failed"))).scalar() or 0
        return {"summary": f"Automation health: {runs} runs, {failed} failed in the last 7 days.",
                "data": {"runs_7d": runs, "failed_7d": failed}}

    # ======================= run history / dashboard / report =======================
    async def runs(self, actor: User, job_key: str | None = None, status_filter: str | None = None,
                   limit: int = 50) -> list[dict]:
        q = select(AutomationRun).filter(AutomationRun.organization_id == actor.organization_id,
                                         AutomationRun.is_deleted == False)
        if job_key:
            q = q.filter(AutomationRun.job_key == job_key)
        if status_filter:
            q = q.filter(AutomationRun.status == status_filter)
        q = q.order_by(AutomationRun.started_at.desc()).limit(min(limit, 200))
        return [self._run_dict(r) for r in (await self.db.execute(q)).scalars().all()]

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        total_runs = (await self.db.execute(select(func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False))).scalar() or 0
        failed = (await self.db.execute(select(func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False,
            AutomationRun.status == "failed"))).scalar() or 0
        by_job = (await self.db.execute(select(AutomationRun.job_key, func.count(AutomationRun.id)).filter(
            AutomationRun.organization_id == org, AutomationRun.is_deleted == False
        ).group_by(AutomationRun.job_key))).all()
        open_breaches = (await self.db.execute(select(func.count(SLABreach.id)).filter(
            SLABreach.organization_id == org, SLABreach.is_deleted == False, SLABreach.resolved == False))).scalar() or 0
        active_reports = (await self.db.execute(select(func.count(ScheduledReport.id)).filter(
            ScheduledReport.organization_id == org, ScheduledReport.is_deleted == False,
            ScheduledReport.is_active == True))).scalar() or 0
        return {"total_runs": total_runs, "failed": failed, "succeeded": total_runs - failed,
                "success_rate": round((total_runs - failed) / total_runs * 100, 1) if total_runs else 100.0,
                "runs_by_job": {k: v for k, v in by_job}, "open_breaches": open_breaches,
                "active_reports": active_reports}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        jobs = await self.list_jobs(actor)
        enabled = sum(1 for j in jobs if j["is_enabled"])
        recent = await self.runs(actor, limit=5)
        return {"jobs": len(jobs), "enabled": enabled, "success_rate": rep["success_rate"],
                "open_breaches": rep["open_breaches"], "active_reports": rep["active_reports"],
                "recent": recent}

    # ---------- serialize ----------
    def _job_dict(self, j: AutomationJob) -> dict:
        return {"id": str(j.id), "job_key": j.job_key, "name": j.name, "category": j.category,
                "description": j.description, "is_enabled": j.is_enabled, "schedule": j.schedule,
                "max_retries": j.max_retries,
                "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
                "last_status": j.last_status,
                "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
                "run_count": j.run_count, "fail_count": j.fail_count}

    def _run_dict(self, r: AutomationRun) -> dict:
        return {"id": str(r.id), "job_key": r.job_key, "status": r.status, "triggered_by": r.triggered_by,
                "items_processed": r.items_processed, "retry_count": r.retry_count, "error": r.error,
                "duration_ms": r.duration_ms,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None}

    def _sla_dict(self, p: SLAPolicy) -> dict:
        return {"id": str(p.id), "name": p.name, "description": p.description, "entity_type": p.entity_type,
                "metric": p.metric, "threshold_hours": p.threshold_hours, "conditions": p.conditions,
                "on_breach": p.on_breach, "is_active": p.is_active, "breach_count": p.breach_count,
                "created_at": p.created_at.isoformat() if p.created_at else None}

    def _breach_dict(self, b: SLABreach) -> dict:
        return {"id": str(b.id), "policy_id": str(b.policy_id), "entity_type": b.entity_type,
                "entity_id": str(b.entity_id), "metric": b.metric, "hours_elapsed": b.hours_elapsed,
                "resolved": b.resolved, "notified": b.notified,
                "breached_at": b.breached_at.isoformat() if b.breached_at else None}

    def _report_dict(self, r: ScheduledReport) -> dict:
        return {"id": str(r.id), "name": r.name, "report_type": r.report_type, "frequency": r.frequency,
                "channel": r.channel, "recipients": r.recipients, "is_active": r.is_active,
                "last_sent_at": r.last_sent_at.isoformat() if r.last_sent_at else None,
                "next_run_at": r.next_run_at.isoformat() if r.next_run_at else None, "send_count": r.send_count}


def _is_uuid(v) -> bool:
    try:
        uuid.UUID(str(v))
        return True
    except (ValueError, TypeError):
        return False

"""Automation Engine scheduled cycle.

Runs the NEW org-scoped automation jobs (SLA breach scan, scheduled reports)
through the tracked runner so each execution is logged with retry / failure
handling. The legacy global crons (lead reminders, escalation, dunning, sms
retry, email sync, campaigns) keep running from main.py unchanged — this cycle
does not re-run them, it complements them.
"""
import logging
from sqlalchemy import select

from app.models.automation import AutomationJob, SLAPolicy, ScheduledReport
from app.services.automation_service import run_tracked

logger = logging.getLogger("app.cron.automation")

# The per-org jobs this cycle owns.
_CYCLE_JOBS = ("sla_scan", "scheduled_reports")


async def run_automation_cycle(session_maker) -> None:
    """Scheduler entry point: for every org that uses the automation engine, run
    its enabled per-org jobs, each in its own session for failure isolation."""
    # discover orgs engaged with the engine (have jobs, SLA policies, or reports)
    async with session_maker() as db:
        org_ids = set()
        for model in (AutomationJob, SLAPolicy, ScheduledReport):
            rows = (await db.execute(select(model.organization_id).filter(
                model.is_deleted == False).distinct())).scalars().all()
            org_ids.update(rows)

    total_runs = 0
    for org_id in org_ids:
        for job_key in _CYCLE_JOBS:
            try:
                async with session_maker() as db:
                    job = await _get_enabled_job(db, org_id, job_key)
                    if job is None:  # not enabled for this org
                        continue
                    await run_tracked(db, org_id, job_key, triggered_by="schedule", job=job)
                    await db.commit()
                    total_runs += 1
            except Exception as e:  # per-job isolation — one failure never stops the cycle
                logger.error("Automation job %s for org %s failed: %s", job_key, org_id, e)
    logger.info("Automation cycle complete: %d job runs across %d orgs", total_runs, len(org_ids))


async def _get_enabled_job(db, org_id, job_key):
    """Return the org's AutomationJob if it's enabled; None if explicitly disabled.
    A not-yet-bootstrapped job defaults to enabled (created on demand)."""
    from app.services.automation_service import AutomationService
    job = (await db.execute(select(AutomationJob).filter(
        AutomationJob.organization_id == org_id, AutomationJob.job_key == job_key,
        AutomationJob.is_deleted == False))).scalars().first()
    if job is not None and not job.is_enabled:
        return None
    if job is None:
        job = await AutomationService(db)._ensure_job(org_id, job_key)
    return job

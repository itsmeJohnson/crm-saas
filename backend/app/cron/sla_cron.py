"""SLA breach-detection cron.

Scans every org's running SLA trackers for response/resolution breaches, records
them and emits `sla.breached` (→ Workflows + Notification rules). Complements the
Automation Engine's lightweight `run_sla_scan`; the two share SLABreach via the
same dedup guard.
"""
import logging
from sqlalchemy import select

from app.models.sla import SLATracker
from app.services.sla_service import SLAService

logger = logging.getLogger("app.cron.sla")


async def run_sla_scan_all(session_maker) -> None:
    """Entry point for the daily loop: scan trackers for every engaged org."""
    async with session_maker() as db:
        org_ids = set((await db.execute(select(SLATracker.organization_id).filter(
            SLATracker.is_deleted == False).distinct())).scalars().all())
    total = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                total += await SLAService(db).scan(org_id)
                await db.commit()
        except Exception as e:
            logger.error("SLA scan for org %s failed: %s", org_id, e)
    if total:
        logger.info("SLA scan flagged %d breach(es) across %d org(s).", total, len(org_ids))

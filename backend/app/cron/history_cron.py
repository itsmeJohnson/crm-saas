"""Historical Analytics cron.

Daily cycle per org: captures today's cross-domain metric snapshot into the
metric_snapshots warehouse (skipped when the org disabled capture), then
applies the retention policy — archiving over-retention daily rows to monthly
averages and pruning them.
"""
import logging
from sqlalchemy import select

from app.models.organization import Organization
from app.models.history import HistorySetting
from app.services.historical_analytics_service import HistoricalAnalyticsService

logger = logging.getLogger("app.cron.history")


async def run_history_capture(session_maker) -> None:
    async with session_maker() as db:
        org_ids = list((await db.execute(select(Organization.id).filter(
            Organization.is_deleted == False))).scalars().all())
        disabled = set((await db.execute(select(HistorySetting.organization_id).filter(
            HistorySetting.capture_enabled == False, HistorySetting.is_deleted == False))).scalars().all())
    captured = pruned = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                svc = HistoricalAnalyticsService(db)
                if org_id not in disabled:
                    out = await svc.capture_org(org_id)
                    captured += 1 if out.get("captured") else 0
                ret = await svc.apply_retention(org_id)
                pruned += ret.get("pruned", 0)
                await db.commit()
        except Exception as e:
            logger.error("History capture for org %s failed: %s", org_id, e)
    if captured or pruned:
        logger.info("Historical analytics: captured %d org snapshot(s), pruned %d archived row(s).",
                    captured, pruned)

"""Export & BI Integration cron.

Daily tick per org: runs every due data-sync config (full or incremental) and
delivers the export to its webhook or cloud-storage destination.
"""
import logging
from sqlalchemy import select

from app.models.bi_export import BISyncConfig
from app.services.bi_export_service import BIExportService

logger = logging.getLogger("app.cron.bi_sync")


async def run_bi_data_sync(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(BISyncConfig.organization_id).filter(
            BISyncConfig.is_active == True, BISyncConfig.is_deleted == False).distinct())).scalars().all())
    synced = failed = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await BIExportService(db).scan(org_id)
                await db.commit()
                synced += out.get("synced", 0)
                failed += out.get("failed", 0)
        except Exception as e:
            logger.error("BI data sync for org %s failed: %s", org_id, e)
    if synced or failed:
        logger.info("BI data sync: %d synced, %d failed across %d org(s).", synced, failed, len(org_ids))

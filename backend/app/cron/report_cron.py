"""Custom Report Builder cron.

Delivers due scheduled report definitions to their recipients (as notifications).
Distinct from the Automation Engine's fixed-type scheduled_reports — this runs
user-built report definitions.
"""
import logging
from sqlalchemy import select

from app.models.report_builder import ReportDefinition
from app.services.report_builder_service import ReportBuilderService

logger = logging.getLogger("app.cron.report")


async def run_scheduled_report_builder(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(ReportDefinition.organization_id).filter(
            ReportDefinition.is_deleted == False, ReportDefinition.schedule_frequency.isnot(None),
            ReportDefinition.next_run.isnot(None)).distinct())).scalars().all())
    total = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                total += await ReportBuilderService(db).run_scheduled(org_id)
                await db.commit()
        except Exception as e:
            logger.error("Scheduled report run for org %s failed: %s", org_id, e)
    if total:
        logger.info("Report builder delivered %d scheduled report(s) across %d org(s).", total, len(org_ids))

"""Scheduled Reports cron.

Daily tick per org: delivers due report schedules (CSV/Excel/PDF over
notification/email/WhatsApp), automatically re-attempting failed cycles up to
each schedule's max_retries before notifying the owner and advancing.
"""
import logging
from sqlalchemy import select

from app.models.scheduled_report import ReportSchedule
from app.services.scheduled_report_service import ScheduledReportService

logger = logging.getLogger("app.cron.scheduled_reports")


async def run_report_schedule_delivery(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(ReportSchedule.organization_id).filter(
            ReportSchedule.is_active == True, ReportSchedule.is_deleted == False).distinct())).scalars().all())
    delivered = failed = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await ScheduledReportService(db).scan(org_id)
                await db.commit()
                delivered += out.get("delivered", 0)
                failed += out.get("failed", 0)
        except Exception as e:
            logger.error("Scheduled report delivery for org %s failed: %s", org_id, e)
    if delivered or failed:
        logger.info("Scheduled reports: %d delivered, %d failed across %d org(s).",
                    delivered, failed, len(org_ids))

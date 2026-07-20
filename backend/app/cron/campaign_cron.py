"""Periodic campaign job: launch due scheduled campaigns and advance running queues."""
import logging

logger = logging.getLogger("app.cron.campaign")


async def run_campaign_check(session_maker) -> None:
    """Scheduler entry point: start scheduled campaigns whose time has arrived and
    process pending batches for running message campaigns."""
    from app.services.campaign_service import process_scheduled_campaigns
    async with session_maker() as db:
        try:
            started = await process_scheduled_campaigns(db)
            await db.commit()
            logger.info("Campaign check: %d scheduled campaigns started", started)
        except Exception as e:
            await db.rollback()
            logger.error("Campaign check failed: %s", e)

"""Periodic SMS job: re-send failed outbound messages that still have retries left."""
import logging

logger = logging.getLogger("app.cron.sms")


async def run_sms_retry_check(session_maker) -> None:
    """Scheduler entry point: retry failed outbound SMS (retry_count < MAX_AUTO_RETRIES)."""
    from app.services.sms_service import SmsService
    async with session_maker() as db:
        try:
            retried = await SmsService(db).retry_failed_batch()
            await db.commit()
            logger.info("SMS retry sweep: %d messages retried", retried)
        except Exception as e:
            await db.rollback()
            logger.error("SMS retry sweep failed: %s", e)

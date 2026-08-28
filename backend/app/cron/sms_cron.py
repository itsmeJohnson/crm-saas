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


async def run_sms_dlr_poll(session_maker) -> None:
    """Scheduler entry point: poll delivery reports for poll-based gateways
    (e.g. BulkSMSPlans, which have no delivery webhook). Updates outbound SMS
    still in a non-terminal state within the lookback window."""
    from app.services.sms_service import SmsService
    async with session_maker() as db:
        try:
            updated = await SmsService(db).poll_delivery_reports()
            await db.commit()
            logger.info("SMS DLR poll: %d messages updated", updated)
        except Exception as e:
            await db.rollback()
            logger.error("SMS DLR poll failed: %s", e)

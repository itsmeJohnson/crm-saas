import logging
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger("app.cron.whatsapp")


async def run_whatsapp_sla_check(session_maker):
    """SLA check running periodically to identify conversations with breached response times."""
    logger.info("Starting periodic WhatsApp SLA checks.")
    async with session_maker() as db:
        try:
            service = WhatsAppService(db)
            result = await service.check_sla_breaches()
            await db.commit()
            logger.info("WhatsApp SLA checks completed. Scanned: %d, Breached: %d", result["scanned"], result["breached"])
        except Exception as e:
            logger.error("WhatsApp SLA check failed: %s", str(e))

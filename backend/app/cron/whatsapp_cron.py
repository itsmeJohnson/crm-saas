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


async def run_whatsapp_hourly_sync(session_maker) -> None:
    """Hourly sync of templates, quality rating, messaging tier, capabilities for all settings."""
    logger.info("Starting periodic WhatsApp hourly synchronization.")
    from sqlalchemy import select
    from app.models.whatsapp import WhatsAppSettings
    
    async with session_maker() as db:
        res = await db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.provider == "meta",
            WhatsAppSettings.is_active == True,
            WhatsAppSettings.is_deleted == False
        ))
        settings_list = list(res.scalars().all())
    
    for s in settings_list:
        try:
            async with session_maker() as db:
                service = WhatsAppService(db)
                await service.sync_settings_metadata(s.id)
                await db.commit()
            logger.info("Synced metadata for WhatsApp settings ID: %s", s.id)
        except Exception as e:
            logger.error("Failed to sync active WhatsApp settings %s: %s", s.id, str(e))

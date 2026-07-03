"""Periodic email job: pull inbound mail via IMAP for every org with a mailbox configured."""
import logging
from sqlalchemy import select

logger = logging.getLogger("app.cron.email")


async def run_email_sync(session_maker) -> None:
    """Scheduler entry point: IMAP-sync every active org mailbox. Records inbound
    emails, notifies owners, and fires email_received workflow rules."""
    from app.models.email_settings import EmailSettings
    from app.services.email_service_module import EmailModuleService
    async with session_maker() as db:
        try:
            org_ids = (await db.execute(select(EmailSettings.organization_id).filter(
                EmailSettings.is_active == True, EmailSettings.is_deleted == False))).scalars().all()
            total = 0
            for org_id in org_ids:
                total += await EmailModuleService(db).sync_inbox(org_id)
            await db.commit()
            logger.info("Email sync: %d inbound emails across %d mailboxes", total, len(org_ids))
        except Exception as e:
            await db.rollback()
            logger.error("Email sync failed: %s", e)

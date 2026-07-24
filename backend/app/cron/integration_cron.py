"""Integration Hub cron.

Health-checks every enabled, hub-owned connection for each org and refreshes the
mirror rows for the channel modules that own their own credentials, so the health
board is accurate without anyone opening the page.
"""
import logging
from sqlalchemy import select

from app.models.organization import Organization
from app.services.integration_service import IntegrationService

logger = logging.getLogger("app.cron.integrations")


async def run_integration_health_checks(session_maker) -> None:
    async with session_maker() as db:
        org_ids = list((await db.execute(select(Organization.id).filter(
            Organization.is_deleted == False))).scalars().all())
    checked = healthy = failed = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await IntegrationService(db).health_check_all(org_id)
                await db.commit()
            checked += out.get("checked", 0)
            healthy += out.get("healthy", 0)
            failed += out.get("failed", 0)
        except Exception as e:
            logger.error("Integration health check for org %s failed: %s", org_id, e)
    if checked:
        logger.info("Integration Hub: checked %d connection(s) — %d healthy, %d failing.",
                    checked, healthy, failed)

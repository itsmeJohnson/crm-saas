"""AI API & SDK cron.

Re-attempts AI webhook deliveries whose exponential backoff has elapsed. A
delivery that exhausts its webhook's max_attempts becomes a dead letter and is
left for manual replay from the Developer Portal.
"""
import logging
from sqlalchemy import select

from app.models.organization import Organization
from app.services.ai_api_service import AIApiService

logger = logging.getLogger("app.cron.ai_webhook")


async def run_ai_webhook_retries(session_maker) -> None:
    async with session_maker() as db:
        org_ids = list((await db.execute(select(Organization.id).filter(
            Organization.is_deleted == False))).scalars().all())
    attempted = delivered = dead = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await AIApiService(db).retry_due_deliveries(org_id)
                await db.commit()
            attempted += out.get("attempted", 0)
            delivered += out.get("delivered", 0)
            dead += out.get("dead_lettered", 0)
        except Exception as e:
            logger.error("AI webhook retry for org %s failed: %s", org_id, e)
    if attempted:
        logger.info("AI webhooks: retried %d delivery(ies) — %d delivered, %d dead-lettered.",
                    attempted, delivered, dead)

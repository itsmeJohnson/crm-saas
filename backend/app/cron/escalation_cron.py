"""Escalation Engine cron.

Runs the configurable multi-level escalation scan for every engaged org. Distinct
from the legacy `run_escalation_scan` (simple idle-lead → manager): this drives
the rule-based, multi-entity, multi-level engine.
"""
import logging
from sqlalchemy import select

from app.models.escalation import EscalationRule
from app.services.escalation_engine_service import EscalationEngineService

logger = logging.getLogger("app.cron.escalation")


async def run_escalation_engine(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(EscalationRule.organization_id).filter(
            EscalationRule.is_active == True, EscalationRule.is_deleted == False).distinct())).scalars().all())
    total = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                total += await EscalationEngineService(db).scan(org_id)
                await db.commit()
        except Exception as e:
            logger.error("Escalation scan for org %s failed: %s", org_id, e)
    if total:
        logger.info("Escalation engine fired %d escalation(s) across %d org(s).", total, len(org_ids))

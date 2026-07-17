"""KPI Engine cron.

Evaluates every org's active KPIs against the live metric snapshot, raising or
resolving threshold-breach alerts (and notifying). Runs once per daily cycle.
"""
import logging
from sqlalchemy import select

from app.models.kpi import KPIDefinition
from app.services.kpi_service import KPIService

logger = logging.getLogger("app.cron.kpi")


async def run_kpi_evaluation(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(KPIDefinition.organization_id).filter(
            KPIDefinition.is_active == True, KPIDefinition.is_deleted == False).distinct())).scalars().all())
    total_raised = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await KPIService(db).evaluate_all(org_id)
                await db.commit()
                total_raised += out.get("raised", 0)
        except Exception as e:
            logger.error("KPI evaluation for org %s failed: %s", org_id, e)
    if total_raised:
        logger.info("KPI engine raised %d alert(s) across %d org(s).", total_raised, len(org_ids))

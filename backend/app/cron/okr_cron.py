"""Goal & OKR Management cron.

Daily cycle per org with active objectives: auto-completes objectives whose key
results have reached 100%, and nudges owners of at-risk objectives as the cycle
end approaches (7/3/1 days out).
"""
import logging
from sqlalchemy import select

from app.models.okr import Objective
from app.services.okr_service import OKRService

logger = logging.getLogger("app.cron.okr")


async def run_okr_scan(session_maker) -> None:
    async with session_maker() as db:
        org_ids = set((await db.execute(select(Objective.organization_id).filter(
            Objective.status == "active", Objective.is_deleted == False).distinct())).scalars().all())
    total_completed = total_nudged = 0
    for org_id in org_ids:
        try:
            async with session_maker() as db:
                out = await OKRService(db).scan(org_id)
                await db.commit()
                total_completed += out.get("completed", 0)
                total_nudged += out.get("nudged", 0)
        except Exception as e:
            logger.error("OKR scan for org %s failed: %s", org_id, e)
    if total_completed or total_nudged:
        logger.info("OKR scan: %d completed, %d at-risk nudge(s) across %d org(s).",
                    total_completed, total_nudged, len(org_ids))

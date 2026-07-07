"""Scheduler tick.

Minute-granularity driver for the configurable Scheduler. Fires every active
schedule across all orgs whose next_run_at has passed, then advances it. Runs as
a dedicated asyncio task from main.py's lifespan, guarded by a redis lock so only
one instance ticks at a time. Complements — does not replace — the legacy daily
midnight loop.
"""
import logging

from app.services.scheduler_service import SchedulerService

logger = logging.getLogger("app.cron.scheduler")


async def run_scheduler_tick(session_maker) -> int:
    """One tick: run all due schedules. Own transaction; returns count fired."""
    async with session_maker() as db:
        try:
            fired = await SchedulerService(db).run_due()
            await db.commit()
            if fired:
                logger.info("Scheduler tick fired %d schedule(s).", fired)
            return fired
        except Exception as e:
            await db.rollback()
            logger.error("Scheduler tick failed: %s", e)
            return 0

"""Periodic calling-platform job: org-wide missed-call sweep.

The /calling/history endpoint also sweeps lazily per-org on read; this cron is
the backstop that catches orgs nobody is looking at.
"""
import logging

logger = logging.getLogger("app.cron.calling")


async def run_missed_call_check(session_maker) -> None:
    """Scheduler entry point: flag stale inbound calls as Missed and notify agents."""
    from app.services.calling_service import CallingService
    async with session_maker() as db:
        try:
            flagged = await CallingService(db).detect_missed_calls()
            await db.commit()
            logger.info("Missed-call sweep: %d calls flagged", flagged)
        except Exception as e:
            await db.rollback()
            logger.error("Missed-call sweep failed: %s", e)

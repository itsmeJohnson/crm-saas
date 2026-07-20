"""Background Queue worker loop.

A poll-based async worker that registers itself, heartbeats, and drains due jobs
across all queues (highest priority first), executing each with the retry / DLQ
machinery in QueueService. Runs as a dedicated asyncio task from main.py's
lifespan, guarded by a redis lock so only one instance drains at a time.
"""
import asyncio
import logging
import socket
import uuid

from app.services.queue_service import QueueService

logger = logging.getLogger("app.cron.queue")

_POLL_INTERVAL = 5.0      # seconds between empty polls
_BATCH = 25               # max jobs drained per wake before yielding


async def run_queue_worker(session_maker) -> None:
    """Long-running worker loop. Cancels cleanly on shutdown."""
    worker_name = f"{socket.gethostname()}:{uuid.uuid4().hex[:6]}"
    worker_id = None
    async with session_maker() as db:
        try:
            w = await QueueService(db).register_worker(worker_name, queues=None)
            worker_id = w.id
            await db.commit()
        except Exception as e:
            logger.error("Queue worker registration failed: %s", e)

    logger.info("Queue worker %s started (id=%s).", worker_name, worker_id)
    while True:
        try:
            processed = await _drain_batch(session_maker, worker_id)
            # heartbeat every cycle even when idle
            if worker_id is not None:
                async with session_maker() as db:
                    await QueueService(db).heartbeat(worker_id, status_val="idle", current_job_id=None)
                    await db.commit()
            if processed == 0:
                await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Queue worker loop error: %s", e)
            await asyncio.sleep(_POLL_INTERVAL)


async def _drain_batch(session_maker, worker_id) -> int:
    """Process up to _BATCH due jobs, each in its own transaction for isolation."""
    processed = 0
    for _ in range(_BATCH):
        async with session_maker() as db:
            svc = QueueService(db)
            job = await svc.process_once(worker_id=worker_id)
            if job is None:
                await db.commit()
                break
            if worker_id is not None:
                await svc.heartbeat(worker_id, status_val="busy",
                                    current_job_id=uuid.UUID(job["id"]), processed_delta=1)
            await db.commit()
            processed += 1
    return processed

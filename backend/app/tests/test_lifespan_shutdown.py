"""Regression guard for BUG-01: a wedged background loop must not stall app
shutdown (the uvicorn --reload "Waiting for application shutdown" hang that
silently killed the reminder/scheduler/queue jobs). The lifespan cancels its
loops and awaits them with a BOUNDED timeout, so shutdown always completes."""
import asyncio
import time

import pytest

import main


async def _uncancellable_loop():
    """A loop that swallows cancellation forever — simulates a task wedged in a
    non-cancellable await (redis lock acquire, long DB op)."""
    while True:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            # deliberately refuse to stop, to prove the bounded wait saves us
            continue


@pytest.mark.asyncio
async def test_shutdown_is_bounded_even_when_a_loop_wont_cancel(monkeypatch):
    # All four background loops refuse to cancel.
    monkeypatch.setattr(main, "subscription_cron_scheduler", _uncancellable_loop)
    monkeypatch.setattr(main, "queue_worker_loop", _uncancellable_loop)
    monkeypatch.setattr(main, "scheduler_tick_loop", _uncancellable_loop)
    monkeypatch.setattr(main, "reminder_dispatch_loop", _uncancellable_loop)
    # Keep the test fast: cap the grace window well below the real 10s.
    monkeypatch.setattr(main, "SHUTDOWN_GRACE_SECONDS", 0.5)

    started = time.monotonic()
    async with main.lifespan(main.app):
        pass  # startup launched the (wedged) loops; exiting triggers shutdown
    elapsed = time.monotonic() - started

    # Without the bounded wait this would hang forever; with it, shutdown returns
    # right after the grace window.
    assert elapsed < 5, f"shutdown took {elapsed:.2f}s — the hang has regressed"


@pytest.mark.asyncio
async def test_shutdown_is_fast_when_loops_cancel_cleanly(monkeypatch):
    async def _clean_loop():
        while True:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break

    for name in ("subscription_cron_scheduler", "queue_worker_loop",
                 "scheduler_tick_loop", "reminder_dispatch_loop"):
        monkeypatch.setattr(main, name, _clean_loop)
    monkeypatch.setattr(main, "SHUTDOWN_GRACE_SECONDS", 10.0)

    started = time.monotonic()
    async with main.lifespan(main.app):
        pass
    elapsed = time.monotonic() - started
    # Well-behaved loops cancel effectively instantly — nowhere near the 10s cap.
    assert elapsed < 2, f"clean shutdown took {elapsed:.2f}s"

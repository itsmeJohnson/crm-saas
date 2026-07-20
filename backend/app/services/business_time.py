"""Pure business-time utilities for SLA timing.

Computes due dates and elapsed time that count only *working* hours — skipping
nights, non-working weekdays and holidays — so a "4h response" SLA raised at
4pm Friday isn't breached over the weekend. Kept dependency-free and pure so it
is trivially unit-testable; the caller supplies the working-day windows (from
WorkingHoursConfig) and the holiday set.

`days` shape (from WorkingHoursConfig): {"mon": {"enabled": bool, "start": "HH:MM",
"end": "HH:MM"}, ...} keyed mon..sun.
"""
from __future__ import annotations
from datetime import datetime, date, time, timedelta

_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DEFAULT_DAYS = {d: {"enabled": i < 5, "start": "09:00", "end": "17:00"} for i, d in enumerate(_WEEKDAYS)}


def _hhmm(s: str | None, default: time) -> time:
    if not s:
        return default
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return default


def _window(days: dict, d: date) -> tuple[time, time] | None:
    """Working window (start, end) for a date, or None if it's a day off."""
    cfg = (days or _DEFAULT_DAYS).get(_WEEKDAYS[d.weekday()])
    if not cfg or not cfg.get("enabled"):
        return None
    start = _hhmm(cfg.get("start"), time(9, 0))
    end = _hhmm(cfg.get("end"), time(17, 0))
    if end <= start:
        return None
    return start, end


def _is_holiday(d: date, holidays: list) -> bool:
    for h in holidays or []:
        # holidays: list of (date, recurring_annual)
        hd, recurring = h if isinstance(h, tuple) else (h, False)
        if recurring:
            if hd.month == d.month and hd.day == d.day:
                return True
        elif hd == d:
            return True
    return False


def add_business_hours(start: datetime, hours: float, days: dict | None = None,
                       holidays: list | None = None, *, max_days: int = 400) -> datetime:
    """Return the datetime `hours` of *working* time after `start` (naive, in the
    org's local tz). Walks day by day, consuming each day's working window."""
    remaining = timedelta(hours=max(0.0, hours))
    if remaining.total_seconds() == 0:
        return start
    cur = start
    for _ in range(max_days):
        win = _window(days, cur.date())
        if win and not _is_holiday(cur.date(), holidays):
            win_start = datetime.combine(cur.date(), win[0])
            win_end = datetime.combine(cur.date(), win[1])
            pos = max(cur, win_start)
            if pos < win_end:
                avail = win_end - pos
                if remaining <= avail:
                    return pos + remaining
                remaining -= avail
        # move to the start of the next day
        cur = datetime.combine(cur.date() + timedelta(days=1), time(0, 0))
    return cur  # ran past the horizon (pathological)


def business_elapsed(start: datetime, end: datetime, days: dict | None = None,
                     holidays: list | None = None, *, max_days: int = 400) -> float:
    """Working hours elapsed between two naive local datetimes."""
    if end <= start:
        return 0.0
    total = timedelta()
    cur = start
    for _ in range(max_days):
        if cur.date() > end.date():
            break
        win = _window(days, cur.date())
        if win and not _is_holiday(cur.date(), holidays):
            win_start = datetime.combine(cur.date(), win[0])
            win_end = datetime.combine(cur.date(), win[1])
            seg_start = max(cur, win_start)
            seg_end = min(end, win_end)
            if seg_end > seg_start:
                total += seg_end - seg_start
        cur = datetime.combine(cur.date() + timedelta(days=1), time(0, 0))
    return round(total.total_seconds() / 3600, 3)

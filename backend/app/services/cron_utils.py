"""Pure, dependency-free cron expression utilities.

Implements the standard 5-field cron format:

    ┌───────────── minute        (0-59)
    │ ┌───────────── hour        (0-23)
    │ │ ┌───────────── day-of-month (1-31)
    │ │ │ ┌───────────── month     (1-12)
    │ │ │ │ ┌───────────── day-of-week (0-6, Sunday=0)
    * * * * *

Each field supports:  *  |  a  |  a,b,c  |  a-b  |  */n  |  a-b/n

`cron_next` returns the next datetime (in the given tz) strictly after `after`
that matches the expression. Kept pure so it is trivially unit-testable — no
external cron library is available in this environment.
"""
from __future__ import annotations
from datetime import datetime, timedelta

_FIELD_BOUNDS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _parse_field(token: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            rng, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError("step must be positive")
        else:
            rng = part
        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, b = rng.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(rng)
        if start < lo or end > hi or start > end:
            raise ValueError(f"field value out of range: {part}")
        values.update(range(start, end + 1, step))
    if not values:
        raise ValueError("empty cron field")
    return values


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Parse a 5-field cron string into per-field allowed-value sets. Raises
    ValueError on malformed input (so callers can validate)."""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron expression must have exactly 5 fields")
    return tuple(_parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, _FIELD_BOUNDS))  # type: ignore


def is_valid_cron(expr: str) -> bool:
    try:
        parse_cron(expr)
        return True
    except (ValueError, TypeError):
        return False


def _matches_parsed(sets, dt: datetime) -> bool:
    minute, hour, dom, month, dow = sets
    if dt.minute not in minute or dt.hour not in hour or dt.month not in month:
        return False
    dom_restricted = len(dom) < 31
    dow_restricted = len(dow) < 7
    py_dow = (dt.weekday() + 1) % 7  # Python Mon=0 → cron Sun=0
    dom_ok = dt.day in dom
    dow_ok = py_dow in dow
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def cron_matches(expr: str, dt: datetime) -> bool:
    """Does `dt` (minute precision) satisfy the cron expression? Day-of-month and
    day-of-week combine with OR when BOTH are restricted (standard cron semantics)."""
    return _matches_parsed(parse_cron(expr), dt)


def cron_next(expr: str, after: datetime, *, horizon_days: int = 366) -> datetime | None:
    """The next minute strictly after `after` that matches `expr`. Returns None if
    no match within the horizon (guards against impossible expressions)."""
    sets = parse_cron(expr)  # parse once, then iterate cheaply
    cur = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = after + timedelta(days=horizon_days)
    while cur <= limit:
        if _matches_parsed(sets, cur):
            return cur
        # skip the rest of a non-matching day in one hop when day/month excludes it
        if cur.month not in sets[3] or not (
                (cur.day in sets[2]) or ((cur.weekday() + 1) % 7 in sets[4])):
            nxt = (cur + timedelta(days=1)).replace(hour=0, minute=0)
            cur = nxt
            continue
        cur += timedelta(minutes=1)
    return None

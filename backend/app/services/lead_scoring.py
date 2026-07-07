"""Rule-based lead scoring.

A deterministic 0-100 heuristic used to prioritise leads. The score is
recomputed whenever scoring-relevant fields change (contactability, deal
value, source quality, priority). Kept intentionally simple and pure so it is
easy to reason about and test; a configurable rules engine can layer on later.
"""
from decimal import Decimal


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute_score(
    *,
    email: str | None = None,
    phone: str | None = None,
    company_name: str | None = None,
    value=None,
    source: str | None = None,
    priority: str | None = None,
) -> int:
    """Return a 0-100 lead score from the supplied attributes."""
    score = 0

    # Contactability
    if email:
        score += 15
    if phone:
        score += 15
    if company_name:
        score += 10

    # Deal value tiers
    v = _to_float(value)
    if v >= 100_000:
        score += 30
    elif v >= 50_000:
        score += 20
    elif v >= 10_000:
        score += 10

    # Source quality
    src = (source or "").strip().lower()
    if src in ("referral", "partner"):
        score += 20
    elif src in ("website", "inbound", "demo request"):
        score += 15
    elif src in ("event", "webinar"):
        score += 10
    elif src:
        score += 5

    # Priority weighting
    prio = (priority or "").strip().lower()
    score += {"urgent": 20, "high": 10, "medium": 5, "low": 0}.get(prio, 0)

    return min(score, 100)

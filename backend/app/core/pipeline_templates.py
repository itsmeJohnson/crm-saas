"""Pipeline templates for tenant provisioning.

ZERO-REGRESSION: with no PIPELINE_TEMPLATE env var (the base CRM and every other
tenant), `default_*` return the original generic pipeline unchanged. Only a
single-tenant instance that sets PIPELINE_TEMPLATE=real_estate (e.g. LoanNest)
gets the vertical pipeline auto-provisioned on org creation.

Stage tuples are (name, order_position, is_system_default) — the same shape the
org repository already seeds. Richer metadata (won/lost/probability/color) is
available via the standalone seed_pipeline_template.py.
"""

from __future__ import annotations

import os

# Original generic default (unchanged from the historical hardcoded list).
DEFAULT_PIPELINE = ("Default Pipeline", "Primary Sales Pipeline")
DEFAULT_STAGES = [
    ("Fresh Leads", 1, True),
    ("Contacted", 2, False),
    ("Followup", 3, False),
    ("Dropped", 4, False),
    ("Converted", 5, False),
]

TEMPLATES: dict[str, dict] = {
    "real_estate": {
        "pipeline": ("Real Estate Sales", "LoanNest 6-stage real-estate & mortgage pipeline"),
        "stages": [
            ("New Property Inquiry", 1, True),
            ("Requirement & Budget Qualified", 2, False),
            ("Site Visit Scheduled / Conducted", 3, False),
            ("Unit Booking & Token Advance", 4, False),
            ("Sale Deed / Disbursement Won", 5, False),
            ("Closed Lost", 6, False),
        ],
    },
}


def active_template() -> str | None:
    """The PIPELINE_TEMPLATE in effect, or None (generic default) if unset/unknown."""
    t = (os.getenv("PIPELINE_TEMPLATE") or "").strip()
    return t if t in TEMPLATES else None


def default_pipeline_meta() -> tuple[str, str]:
    t = active_template()
    return TEMPLATES[t]["pipeline"] if t else DEFAULT_PIPELINE


def default_stages() -> list[tuple[str, int, bool]]:
    t = active_template()
    return TEMPLATES[t]["stages"] if t else DEFAULT_STAGES

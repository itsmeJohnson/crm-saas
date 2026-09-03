"""
Optional pipeline-template seeder (single-tenant client provisioning).

ZERO-REGRESSION: this is a standalone script. It is never imported by the app and
does nothing unless you run it AND pass a known --template. The base CRM and other
tenants are untouched.

Usage:
    # Real-estate 6-stage pipeline for one org (e.g. LoanNest):
    python seed_pipeline_template.py --template=real_estate --org-id=<ORG_UUID>

    # Or drive the template from the environment instead of the flag:
    PIPELINE_TEMPLATE=real_estate python seed_pipeline_template.py --org-id=<ORG_UUID>

    # Dry run (prints the plan, writes nothing):
    python seed_pipeline_template.py --template=real_estate --org-id=<ORG_UUID> --dry-run

Idempotent: if a pipeline with the same name already exists for the org, it is
skipped (no duplicate, no overwrite).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.pipeline import Pipeline, PipelineStage


# ── Templates ─────────────────────────────────────────────────────────────────
# Each stage: (name, probability%, color, is_won, is_lost)
TEMPLATES: dict[str, dict] = {
    "real_estate": {
        "pipeline_name": "Real Estate Sales",
        "description": "LoanNest 6-stage real-estate & mortgage pipeline",
        "stages": [
            ("New Property Inquiry",              5,  "#3B82F6", False, False),
            ("Requirement & Budget Qualified",   20,  "#6366F1", False, False),
            ("Site Visit Scheduled / Conducted", 45,  "#8B5CF6", False, False),
            ("Unit Booking & Token Advance",     70,  "#F59E0B", False, False),
            ("Sale Deed / Disbursement Won",    100,  "#10B981", True,  False),
            ("Closed Lost",                       0,  "#EF4444", False, True),
        ],
    },
}


def _resolve_template(cli_value: str | None) -> str | None:
    tpl = cli_value or os.getenv("PIPELINE_TEMPLATE")
    if not tpl:
        return None
    if tpl not in TEMPLATES:
        sys.exit(f"Unknown template '{tpl}'. Known: {', '.join(TEMPLATES)}")
    return tpl


async def seed(template: str, org_id: uuid.UUID, dry_run: bool) -> None:
    spec = TEMPLATES[template]
    print(f"[seed] template={template} org={org_id} dry_run={dry_run}")
    print(f"[seed] pipeline '{spec['pipeline_name']}' with {len(spec['stages'])} stages")
    for i, (name, prob, color, won, lost) in enumerate(spec["stages"], start=1):
        print(f"        {i}. {name:38s} p={prob:3d}%  won={won} lost={lost}")
    if dry_run:
        print("[seed] dry-run — nothing written.")
        return

    async with async_session_maker() as session:
        existing = await session.scalar(
            select(Pipeline).where(
                Pipeline.organization_id == org_id,
                Pipeline.name == spec["pipeline_name"],
            )
        )
        if existing:
            print(f"[seed] pipeline '{spec['pipeline_name']}' already exists for org — skipping.")
            return

        pipeline = Pipeline(
            organization_id=org_id,
            name=spec["pipeline_name"],
            description=spec["description"],
            is_default=False,   # never override the org's existing default pipeline
            is_active=True,
        )
        session.add(pipeline)
        await session.flush()  # get pipeline.id

        for pos, (name, prob, color, won, lost) in enumerate(spec["stages"], start=1):
            session.add(PipelineStage(
                organization_id=org_id,
                pipeline_id=pipeline.id,
                name=name,
                order_position=pos,
                color=color,
                probability=prob,
                is_won=won,
                is_lost=lost,
                is_system_default=False,
                is_active=True,
            ))
        await session.commit()
        print(f"[seed] created pipeline {pipeline.id} with {len(spec['stages'])} stages.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Optional pipeline-template seeder.")
    ap.add_argument("--template", default=None, help="e.g. real_estate (or set PIPELINE_TEMPLATE)")
    ap.add_argument("--org-id", default=None, help="target organization UUID")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    template = _resolve_template(args.template)
    if not template:
        print("No template selected (pass --template=real_estate or PIPELINE_TEMPLATE). Nothing to do.")
        return
    if not args.org_id:
        sys.exit("--org-id is required to seed a pipeline.")
    try:
        org_id = uuid.UUID(args.org_id)
    except ValueError:
        sys.exit(f"--org-id is not a valid UUID: {args.org_id}")

    asyncio.run(seed(template, org_id, args.dry_run))


if __name__ == "__main__":
    main()

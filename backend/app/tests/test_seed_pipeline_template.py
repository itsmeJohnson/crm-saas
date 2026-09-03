"""Guards for the optional pipeline-template seeder (seed_pipeline_template.py).

Contract:
  • No template selected  -> writes nothing (base CRM / other tenants untouched).
  • --dry-run             -> writes nothing.
  • real_estate template  -> exactly one pipeline + 6 stages, non-default,
                             with the correct won/lost flags.
  • Re-running            -> idempotent (no duplicate pipeline/stages).

The seeder calls app.core.database.async_session_maker directly, so we point that
name at the conftest's in-memory test session for the duration of each test.
"""
import uuid

import pytest
from sqlalchemy import select

import seed_pipeline_template as seed_mod
from app.models.pipeline import Pipeline, PipelineStage

PIPELINE_NAME = "Real Estate Sales"


class _SharedSessionCM:
    """Async CM that hands the seeder the shared test session and never closes it,
    so a second seed() run in the same test sees the first run's committed rows."""
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def use_test_session(db, monkeypatch):
    monkeypatch.setattr(seed_mod, "async_session_maker", lambda: _SharedSessionCM(db))
    return db


async def _pipelines_for(db, org_id):
    rows = await db.scalars(select(Pipeline).where(Pipeline.organization_id == org_id))
    return list(rows)


async def _stages_for(db, pipeline_id):
    rows = await db.scalars(select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id))
    return list(rows)


# ── Template resolution (pure, no DB) ─────────────────────────────────────────
def test_resolve_template_none_when_unset(monkeypatch):
    monkeypatch.delenv("PIPELINE_TEMPLATE", raising=False)
    assert seed_mod._resolve_template(None) is None


def test_resolve_template_from_env(monkeypatch):
    monkeypatch.setenv("PIPELINE_TEMPLATE", "real_estate")
    assert seed_mod._resolve_template(None) == "real_estate"


def test_resolve_template_unknown_exits(monkeypatch):
    monkeypatch.delenv("PIPELINE_TEMPLATE", raising=False)
    with pytest.raises(SystemExit):
        seed_mod._resolve_template("nope_not_a_template")


# ── Seeding behaviour (DB-backed) ─────────────────────────────────────────────
async def test_dry_run_writes_nothing(use_test_session):
    db = use_test_session
    org_id = uuid.uuid4()
    await seed_mod.seed("real_estate", org_id, dry_run=True)
    assert await _pipelines_for(db, org_id) == [], "dry-run must not write any pipeline"


async def test_seed_creates_pipeline_and_six_stages(use_test_session):
    db = use_test_session
    org_id = uuid.uuid4()
    await seed_mod.seed("real_estate", org_id, dry_run=False)

    pipelines = await _pipelines_for(db, org_id)
    assert len(pipelines) == 1
    pipeline = pipelines[0]
    assert pipeline.name == PIPELINE_NAME
    assert pipeline.is_default is False, "must never override the org's default pipeline"
    assert pipeline.is_active is True

    stages = await _stages_for(db, pipeline.id)
    assert len(stages) == 6
    # Order positions are 1..6 and unique
    assert sorted(s.order_position for s in stages) == [1, 2, 3, 4, 5, 6]
    # Exactly one won stage and one lost stage
    assert sum(1 for s in stages if s.is_won) == 1
    assert sum(1 for s in stages if s.is_lost) == 1
    won = next(s for s in stages if s.is_won)
    lost = next(s for s in stages if s.is_lost)
    assert won.name == "Sale Deed / Disbursement Won"
    assert lost.name == "Closed Lost"


async def test_seed_is_idempotent(use_test_session):
    db = use_test_session
    org_id = uuid.uuid4()
    await seed_mod.seed("real_estate", org_id, dry_run=False)
    await seed_mod.seed("real_estate", org_id, dry_run=False)  # second run

    pipelines = await _pipelines_for(db, org_id)
    assert len(pipelines) == 1, "re-running must not create a duplicate pipeline"
    stages = await _stages_for(db, pipelines[0].id)
    assert len(stages) == 6, "re-running must not duplicate stages"


async def test_seed_scopes_to_its_org_only(use_test_session):
    """Seeding org A must not create anything under an unrelated org B."""
    db = use_test_session
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await seed_mod.seed("real_estate", org_a, dry_run=False)
    assert len(await _pipelines_for(db, org_a)) == 1
    assert await _pipelines_for(db, org_b) == []

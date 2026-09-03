"""Org-creation is pipeline-template aware.

Base CRM / other tenants (no PIPELINE_TEMPLATE) -> unchanged 5-stage generic
pipeline. A single-tenant instance with PIPELINE_TEMPLATE=real_estate -> the
6-stage real-estate pipeline auto-provisioned on org create.
"""
import importlib

import pytest
from sqlalchemy import select

from app.repositories.organization import OrganizationRepository
from app.models.pipeline import Pipeline, PipelineStage


async def _stage_names(db, org_id):
    pipeline = await db.scalar(select(Pipeline).where(Pipeline.organization_id == org_id))
    assert pipeline is not None and pipeline.is_default is True
    stages = list(await db.scalars(select(PipelineStage).where(PipelineStage.pipeline_id == pipeline.id)))
    return pipeline.name, sorted(stages, key=lambda s: s.order_position)


async def test_default_org_gets_generic_pipeline(db, monkeypatch):
    monkeypatch.delenv("PIPELINE_TEMPLATE", raising=False)
    import app.core.pipeline_templates as tpl
    importlib.reload(tpl)  # re-read env

    org = await OrganizationRepository(db).create({"name": "Generic Co", "slug": "generic-co-tpl"})
    name, stages = await _stage_names(db, org.id)
    assert name == "Default Pipeline"
    assert [s.name for s in stages] == ["Fresh Leads", "Contacted", "Followup", "Dropped", "Converted"]


async def test_real_estate_instance_gets_vertical_pipeline(db, monkeypatch):
    monkeypatch.setenv("PIPELINE_TEMPLATE", "real_estate")
    import app.core.pipeline_templates as tpl
    importlib.reload(tpl)
    try:
        org = await OrganizationRepository(db).create({"name": "LoanNest Co", "slug": "loannest-co-tpl"})
        name, stages = await _stage_names(db, org.id)
        assert name == "Real Estate Sales"
        assert len(stages) == 6
        assert stages[0].name == "New Property Inquiry"
        assert stages[-1].name == "Closed Lost"
    finally:
        monkeypatch.delenv("PIPELINE_TEMPLATE", raising=False)
        importlib.reload(tpl)  # restore generic default for the rest of the suite

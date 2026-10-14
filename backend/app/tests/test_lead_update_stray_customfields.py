"""Regression: a lead carrying unregistered custom_field keys must stay updatable.

Web-form capture used to write UTM / landing_page into custom_fields. Those keys
have no field definition, so every later update (drag-drop stage change, edit)
was rejected with "Unknown custom field key" — bricking the Kanban. The update
path now drops such stray keys instead of 400-ing; the create path stays strict.
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.services.lead_service import LeadService


async def _seed(db: AsyncSession, slug: str):
    org = await OrganizationRepository(db).create({"name": slug, "slug": slug})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    pipe = Pipeline(organization_id=org.id, name="Sales", is_default=True, is_active=True)
    db.add(pipe)
    await db.commit()
    s1 = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New", order_position=1, is_system_default=True)
    s2 = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="Contacted", order_position=2)
    db.add_all([s1, s2])
    await db.commit()
    return org, admin, s1, s2


@pytest.mark.asyncio
async def test_stage_change_survives_stray_custom_fields(db: AsyncSession):
    org, admin, s1, s2 = await _seed(db, "stray-a")
    svc = LeadService(db, org.id)
    lead = await svc.create_lead(admin, {"last_name": "Web", "title": "Website Lead",
                                         "stage_id": s1.id, "pipeline_id": s1.pipeline_id})
    # Simulate a capture-polluted lead: stray keys written straight to the column.
    row = (await db.execute(select(Lead).filter(Lead.id == lead.id))).scalar_one()
    row.custom_fields = {"landing_page": "skyline", "utm_source": "google"}
    db.add(row)
    await db.commit()

    # The move that drag-drop performs must succeed (was a 400 before the fix)…
    updated = await svc.update_lead(admin, lead.id, {"stage_id": s2.id})
    assert updated.stage_id == s2.id
    # …and the stray keys are dropped in passing.
    assert updated.custom_fields in (None, {}) or "landing_page" not in updated.custom_fields


@pytest.mark.asyncio
async def test_create_still_rejects_unknown_custom_field(db: AsyncSession):
    org, admin, s1, s2 = await _seed(db, "stray-b")
    svc = LeadService(db, org.id)
    with pytest.raises(HTTPException) as ei:
        await svc.create_lead(admin, {"last_name": "X", "title": "T", "stage_id": s1.id,
                                      "pipeline_id": s1.pipeline_id,
                                      "custom_fields": {"not_a_real_field": "nope"}})
    assert ei.value.status_code == 400
    assert "custom field" in str(ei.value.detail).lower()

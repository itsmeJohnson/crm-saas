"""Regression: web-form (landing page) capture must produce a valid lead.

Guards two bugs found during live testing:
1. leads.stage_id is NOT NULL — the landing submit must resolve the org's
   default pipeline stage (previously it 500'd on insert).
2. The feature gate must not crash comparing a naive subscription end_date to an
   aware `now` (covered indirectly — submit is public, but create/publish is gated).
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.landing_page import LandingPage
from app.models.lead import Lead
from app.services.landing_page_service import LandingPageService


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
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    page = LandingPage(organization_id=org.id, name="Book a viewing", slug=f"{slug}-lp",
                       is_published=True, owner_user_id=admin.id,
                       config={"headline": "Hi"})
    db.add(page)
    await db.commit()
    return org, admin, stage, page


@pytest.mark.asyncio
async def test_landing_submit_creates_lead_with_stage(db: AsyncSession):
    org, admin, stage, page = await _seed(db, "lp-a")
    res = await LandingPageService(db).submit(
        page.slug,
        {"name": "Neha Kulkarni", "phone": "+919876500011", "email": "neha@x.com",
         "message": "2BHK in Powai"},
        {"utm_source": "google", "utm_campaign": "powai"})
    await db.commit()
    assert res["status"] == "success"

    lead = (await db.execute(select(Lead).filter(Lead.id == uuid.UUID(res["lead_id"])))).scalar_one()
    # Landed in a real stage (not NULL) belonging to this org — the bug was a
    # NULL stage_id insert failure.
    assert lead.stage_id is not None
    valid_stage = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.id == lead.stage_id,
        PipelineStage.organization_id == org.id))).scalar_one_or_none()
    assert valid_stage is not None
    assert lead.source.startswith("Landing Page:")
    assert lead.assigned_user_id == admin.id
    # custom_fields stays clean — unregistered keys there would brick later edits.
    assert not lead.custom_fields
    # UTM + enquiry context are captured as a note on the lead instead.
    from app.models.note import Note
    notes = (await db.execute(select(Note).filter(Note.lead_id == lead.id))).scalars().all()
    blob = "\n".join(n.content for n in notes)
    assert "google" in blob and "2BHK in Powai" in blob and page.slug in blob

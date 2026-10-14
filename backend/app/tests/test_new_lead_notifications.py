"""Feature 9 — new-lead notifications.

The moment an inbound lead lands it must alert the responsible owner (in-app,
plus email/SMS/push per prefs). Manually-typed leads must NOT self-spam the
creator. Covers the service-level contract that both capture paths rely on.
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.notification import Notification
from app.services.lead_service import LeadService


async def _seed(db: AsyncSession, slug: str):
    org = await OrganizationRepository(db).create({"name": slug, "slug": slug})
    await db.commit()
    owner = await UserRepository(db).create_user(org.id, {
        "email": f"owner@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ola", "last_name": "Owner", "role": "OrgAdmin", "is_active": True})
    rep = await UserRepository(db).create_user(org.id, {
        "email": f"rep@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Rae", "last_name": "Rep", "role": "Employee", "is_active": True})
    await db.commit()
    pipe = Pipeline(organization_id=org.id, name="Sales", is_default=True, is_active=True)
    db.add(pipe)
    await db.commit()
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    await db.commit()
    return org, owner, rep, stage


async def _lead_notifs(db, org_id, user_id):
    rows = (await db.execute(select(Notification).filter(
        Notification.organization_id == org_id,
        Notification.user_id == user_id,
        Notification.category == "lead"))).scalars().all()
    return rows


@pytest.mark.asyncio
async def test_inbound_lead_alerts_owner_even_when_self_owned(db: AsyncSession):
    org, owner, rep, stage = await _seed(db, "inbound-a")
    svc = LeadService(db, org.id)
    lead = await svc.create_lead(owner, {
        "last_name": "Prospect", "title": "Website enquiry", "source": "Landing Page: Demo",
        "stage_id": stage.id, "pipeline_id": stage.pipeline_id,
    }, inbound=True)
    await db.commit()

    notifs = await _lead_notifs(db, org.id, owner.id)
    assert len(notifs) == 1, "owner should be alerted for an inbound lead they own"
    n = notifs[0]
    assert n.title == "New lead captured"
    assert n.priority == "high"
    assert n.action_metadata.get("lead_id") == str(lead.id)


@pytest.mark.asyncio
async def test_manual_self_created_lead_does_not_notify(db: AsyncSession):
    org, owner, rep, stage = await _seed(db, "manual-b")
    svc = LeadService(db, org.id)
    await svc.create_lead(rep, {
        "last_name": "Typed", "title": "Cold call", "assigned_user_id": rep.id,
        "stage_id": stage.id, "pipeline_id": stage.pipeline_id,
    }, inbound=False)
    await db.commit()

    assert await _lead_notifs(db, org.id, rep.id) == [], "no self-spam for manually-typed own leads"


@pytest.mark.asyncio
async def test_manual_assignment_alerts_the_assignee(db: AsyncSession):
    org, owner, rep, stage = await _seed(db, "assign-c")
    svc = LeadService(db, org.id)
    await svc.create_lead(owner, {
        "last_name": "Handoff", "title": "Manager-created", "assigned_user_id": rep.id,
        "stage_id": stage.id, "pipeline_id": stage.pipeline_id,
    }, inbound=False)
    await db.commit()

    rep_notifs = await _lead_notifs(db, org.id, rep.id)
    assert len(rep_notifs) == 1 and rep_notifs[0].title == "New lead assigned to you"
    assert await _lead_notifs(db, org.id, owner.id) == [], "creator is not alerted for their own handoff"

"""Feature 8 — duplicate lead detection & merge.

Detection (find_duplicates by shared email/phone) already existed; these cover
the new merge: the surviving lead adopts the other's children and blank fields,
and the merged-away lead is soft-deleted.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.models.lead_reminder import LeadReminder
from fastapi import HTTPException
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
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    await db.commit()
    return org, admin, stage


async def _mk_lead(db, svc, actor, stage, **over):
    data = {"last_name": "Lead", "title": "T", "stage_id": stage.id,
            "pipeline_id": stage.pipeline_id, **over}
    lead = await svc.create_lead(actor, data)
    await db.commit()
    return lead


@pytest.mark.asyncio
async def test_find_duplicates_matches_shared_phone(db: AsyncSession):
    org, admin, stage = await _seed(db, "dup-a")
    svc = LeadService(db, org.id)
    await _mk_lead(db, svc, admin, stage, phone="+919000000001", email="a@x.com")
    await _mk_lead(db, svc, admin, stage, phone="+919000000001", email="b@x.com")
    dups = await svc.find_duplicates(admin, phone="+919000000001")
    assert len(dups) == 2


@pytest.mark.asyncio
async def test_merge_folds_children_and_soft_deletes_secondary(db: AsyncSession):
    org, admin, stage = await _seed(db, "merge-b")
    svc = LeadService(db, org.id)
    primary = await _mk_lead(db, svc, admin, stage, last_name="Keep", phone="+911111111111")
    secondary = await _mk_lead(db, svc, admin, stage, last_name="Drop",
                               phone="+911111111111", email="found@x.com", city="Pune")

    # A reminder that lives on the secondary must survive on the primary.
    rem = LeadReminder(organization_id=org.id, lead_id=secondary.id, user_id=admin.id,
                       remind_at=datetime.now(timezone.utc), note="call back", created_by=admin.id)
    db.add(rem)
    await db.commit()

    merged = await svc.merge_leads(admin, primary.id, secondary.id)
    await db.commit()

    # Blank scalar (email/city) filled from secondary; identity kept.
    assert merged.last_name == "Keep"
    assert merged.email == "found@x.com"
    assert merged.city == "Pune"

    # Reminder re-pointed onto the primary.
    moved = (await db.execute(select(LeadReminder).filter(LeadReminder.id == rem.id))).scalar_one()
    assert moved.lead_id == primary.id

    # Secondary soft-deleted and no longer visible.
    gone = (await db.execute(select(Lead).filter(Lead.id == secondary.id))).scalar_one()
    assert gone.is_deleted is True


@pytest.mark.asyncio
async def test_merge_rejects_self_merge(db: AsyncSession):
    org, admin, stage = await _seed(db, "merge-self")
    svc = LeadService(db, org.id)
    lead = await _mk_lead(db, svc, admin, stage)
    with pytest.raises(HTTPException) as ei:
        await svc.merge_leads(admin, lead.id, lead.id)
    assert ei.value.status_code == 400

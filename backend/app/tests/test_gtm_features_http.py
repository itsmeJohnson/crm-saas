"""End-to-end HTTP smoke tests for the go-to-market gap features.

Exercises the real routers (registration, schemas, auth) through the ASGI app —
booking (admin + public), email sequences (CRUD + enroll), lead merge, and the
duplicate-lookup endpoint — as a client would actually call them.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage


@pytest.fixture
async def env(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "GTM Co", "slug": "gtm-co"})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": "admin@gtm-co.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    pipe = Pipeline(organization_id=org.id, name="Sales", is_default=True, is_active=True)
    db.add(pipe)
    await db.commit()
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    await db.commit()
    return {"org": org, "admin": admin, "stage": stage,
            "h": {"Authorization": f"Bearer {create_access_token(admin.id)}"}}


async def _make_lead(client, h, stage, **over):
    body = {"last_name": "Lead", "title": "T", "stage_id": str(stage.id),
            "pipeline_id": str(stage.pipeline_id), **over}
    r = await client.post("/api/v1/leads/", json=body, headers=h)
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.mark.asyncio
async def test_booking_admin_then_public_flow(env, client: AsyncClient):
    h, stage = env["h"], env["stage"]
    # Admin creates a booking link.
    r = await client.post("/api/v1/booking/links", json={"title": "Demo call", "slot_minutes": 30}, headers=h)
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]

    # Public page + availability need no auth.
    r = await client.get(f"/api/v1/public/booking/{slug}")
    assert r.status_code == 200 and r.json()["title"] == "Demo call"

    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).date()
    r = await client.get(f"/api/v1/public/booking/{slug}/availability",
                         params={"date_from": today.isoformat(), "date_to": (today + timedelta(days=10)).isoformat()})
    assert r.status_code == 200, r.text
    slots = [s for d in r.json()["days"] for s in d["slots"]]
    assert slots, "expected open slots"

    # Public booking creates the appointment + lead.
    r = await client.post(f"/api/v1/public/booking/{slug}/book",
                          json={"slot_start": slots[0], "name": "Val Visitor", "email": "val@x.com"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_email_sequence_crud_and_enroll(env, client: AsyncClient):
    h, stage = env["h"], env["stage"]
    r = await client.post("/api/v1/email-sequences", json={
        "name": "Nurture", "trigger": "manual",
        "steps": [{"subject": "Hi {{first_name}}", "body": "Welcome", "delay_hours": 0}]}, headers=h)
    assert r.status_code == 201, r.text
    seq_id = r.json()["id"]
    assert len(r.json()["steps"]) == 1

    lead = await _make_lead(client, h, stage, email="enrol@x.com")
    r = await client.post(f"/api/v1/email-sequences/{seq_id}/enroll", json={"lead_id": lead["id"]}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"

    r = await client.get(f"/api/v1/email-sequences/{seq_id}/enrollments", headers=h)
    assert r.status_code == 200 and len(r.json()) == 1


@pytest.mark.asyncio
async def test_duplicate_lookup_and_merge(env, client: AsyncClient):
    h, stage = env["h"], env["stage"]
    a = await _make_lead(client, h, stage, last_name="Keep", phone="+919812345678")
    b = await _make_lead(client, h, stage, last_name="Drop", phone="+919812345678", email="dup@x.com")

    # Duplicate lookup surfaces both.
    r = await client.get("/api/v1/leads/duplicates", params={"phone": "+919812345678"}, headers=h)
    assert r.status_code == 200 and len(r.json()) == 2

    # Merge folds b into a.
    r = await client.post("/api/v1/leads/merge", json={"primary_id": a["id"], "secondary_id": b["id"]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "dup@x.com"  # blank field filled from secondary

    # Secondary no longer returned by the duplicate lookup.
    r = await client.get("/api/v1/leads/duplicates", params={"phone": "+919812345678"}, headers=h)
    assert len(r.json()) == 1

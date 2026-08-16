"""Regression tests for inbound lead capture (ad-platform / web-form -> Lead).

Covers the generic webhook, Meta Lead Ads, Google Ads, HMAC signing,
idempotency, source attribution, owner attribution, RBAC and tenant isolation.
"""
import json
import hmac
import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead


async def _seed_org(db: AsyncSession, name: str, slug: str):
    org = await OrganizationRepository(db).create({"name": name, "slug": slug})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    emp = await UserRepository(db).create_user(org.id, {
        "email": f"emp@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Eve", "last_name": "Employee", "role": "Employee", "is_active": True})
    await db.commit()
    pipe = Pipeline(organization_id=org.id, name="Sales", is_default=True, is_active=True)
    db.add(pipe)
    await db.commit()
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    await db.commit()
    return org, admin, emp, pipe


@pytest.fixture
async def env(db: AsyncSession):
    org, admin, emp, pipe = await _seed_org(db, "Clinic A", "clinic-a")
    return {
        "org": org, "admin": admin, "emp": emp, "pipe": pipe,
        "admin_h": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "emp_h": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _make_source(client, headers, **overrides):
    body = {"name": "Meta Instagram Ads", "provider": "generic",
            "source_label": "Instagram Ads", **overrides}
    r = await client.post("/api/v1/lead-capture/sources", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _count_leads(db, org_id) -> int:
    rows = (await db.execute(select(Lead).filter(Lead.organization_id == org_id))).scalars().all()
    return len(rows)


# ---------------- admin CRUD + RBAC ----------------
@pytest.mark.asyncio
async def test_create_source_returns_webhook_url(client: AsyncClient, env):
    src = await _make_source(client, env["admin_h"])
    assert src["token"]
    assert src["webhook_url"].endswith(f"/lead-capture/inbound/{src['token']}")
    assert src["source_label"] == "Instagram Ads"
    assert src["has_secret"] is False


@pytest.mark.asyncio
async def test_employee_cannot_manage_sources(client: AsyncClient, env):
    r = await client.post("/api/v1/lead-capture/sources",
                          json={"name": "x", "source_label": "y"}, headers=env["emp_h"])
    assert r.status_code == 403


# ---------------- generic ingest ----------------
@pytest.mark.asyncio
async def test_generic_inbound_creates_attributed_lead(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"])
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}",
                          json={"full_name": "Priya Sharma", "email": "priya@example.com",
                                "phone_number": "+919812345678", "treatment": "Braces consult",
                                "id": "web-123"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created"
    lead = (await db.execute(select(Lead).filter(Lead.email == "priya@example.com"))).scalar_one()
    assert lead.first_name == "Priya" and lead.last_name == "Sharma"
    assert lead.phone == "+919812345678"
    assert lead.source == "Instagram Ads"          # attributed to the source label
    assert lead.title == "Braces consult"
    assert lead.created_by == env["admin"].id       # owned by the source owner


@pytest.mark.asyncio
async def test_generic_custom_field_mapping(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"],
                             field_mapping={"Correo": "email", "Telefono": "phone", "Nombre": "last_name"})
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}",
                          json={"Nombre": "Gomez", "Correo": "g@example.com", "Telefono": "+34999", "id": "es-1"})
    assert r.status_code == 200
    lead = (await db.execute(select(Lead).filter(Lead.email == "g@example.com"))).scalar_one()
    assert lead.last_name == "Gomez" and lead.phone == "+34999"


@pytest.mark.asyncio
async def test_idempotency_same_external_id(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"])
    payload = {"full_name": "Repeat Lead", "email": "dup@example.com", "id": "meta-777"}
    r1 = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", json=payload)
    r2 = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", json=payload)
    assert r1.json()["status"] == "created"
    assert r2.json()["status"] == "duplicate"
    assert r2.json()["lead_id"] == r1.json()["lead_id"]
    leads = (await db.execute(select(Lead).filter(Lead.email == "dup@example.com"))).scalars().all()
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_unknown_token_404(client: AsyncClient, env):
    r = await client.post("/api/v1/lead-capture/inbound/not-a-real-token", json={"email": "x@y.com"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_inactive_source_404(client: AsyncClient, env):
    src = await _make_source(client, env["admin_h"])
    await client.patch(f"/api/v1/lead-capture/sources/{src['id']}", json={"is_active": False}, headers=env["admin_h"])
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", json={"email": "x@y.com"})
    assert r.status_code == 404


# ---------------- HMAC signature ----------------
@pytest.mark.asyncio
async def test_hmac_signature_enforced(client: AsyncClient, env):
    src = await _make_source(client, env["admin_h"], secret="s3cr3t")
    body = json.dumps({"full_name": "Signed Lead", "email": "s@example.com", "id": "sig-1"}).encode()
    good = hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()

    # missing signature -> 401
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", content=body,
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 401
    # wrong signature -> 401
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", content=body,
                          headers={"Content-Type": "application/json", "X-Signature": "deadbeef"})
    assert r.status_code == 401
    # correct signature -> 200
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", content=body,
                          headers={"Content-Type": "application/json", "X-Signature": good})
    assert r.status_code == 200 and r.json()["status"] == "created"


# ---------------- Meta Lead Ads ----------------
@pytest.mark.asyncio
async def test_meta_verify_handshake(client: AsyncClient, env):
    src = await _make_source(client, env["admin_h"], provider="meta_lead_ads",
                             source_label="Facebook Ads", meta_verify_token="verify-me")
    ok = await client.get(f"/api/v1/lead-capture/meta/{src['token']}",
                          params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = await client.get(f"/api/v1/lead-capture/meta/{src['token']}",
                           params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"})
    assert bad.status_code == 403


@pytest.mark.asyncio
async def test_meta_leadgen_creates_lead(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"], provider="meta_lead_ads", source_label="Facebook Ads")
    payload = {"object": "page", "entry": [{"id": "PAGE", "changes": [{"field": "leadgen", "value": {
        "leadgen_id": "LG-1001", "form_id": "F1", "page_id": "PAGE",
        "field_data": [
            {"name": "full_name", "values": ["Rahul Verma"]},
            {"name": "email", "values": ["rahul@example.com"]},
            {"name": "phone_number", "values": ["+919800011122"]},
        ]}}]}]}
    r = await client.post(f"/api/v1/lead-capture/meta/{src['token']}", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created"
    lead = (await db.execute(select(Lead).filter(Lead.email == "rahul@example.com"))).scalar_one()
    assert lead.first_name == "Rahul" and lead.last_name == "Verma"
    assert lead.phone == "+919800011122" and lead.source == "Facebook Ads"
    # replay same leadgen_id -> duplicate
    r2 = await client.post(f"/api/v1/lead-capture/meta/{src['token']}", json=payload)
    assert r2.json()["status"] == "duplicate"


# ---------------- Google Ads ----------------
@pytest.mark.asyncio
async def test_google_ads_lead_form(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"], provider="google_ads", source_label="Google Ads")
    payload = {"lead_id": "G-555", "form_id": "gf1", "user_column_data": [
        {"column_name": "Full Name", "string_value": "Neha Gupta"},
        {"column_name": "Email", "string_value": "neha@example.com"},
        {"column_name": "Phone Number", "string_value": "+919700022233"},
    ]}
    r = await client.post(f"/api/v1/lead-capture/inbound/{src['token']}", json=payload)
    assert r.status_code == 200, r.text
    lead = (await db.execute(select(Lead).filter(Lead.email == "neha@example.com"))).scalar_one()
    assert lead.last_name == "Gupta" and lead.source == "Google Ads"


# ---------------- tenant isolation ----------------
@pytest.mark.asyncio
async def test_cross_tenant_source_not_visible(client: AsyncClient, env, db):
    src = await _make_source(client, env["admin_h"])
    org_b, admin_b, _, _ = await _seed_org(db, "Clinic B", "clinic-b")
    other_h = {"Authorization": f"Bearer {create_access_token(admin_b.id)}"}
    r = await client.get(f"/api/v1/lead-capture/sources/{src['id']}", headers=other_h)
    assert r.status_code == 404
    # and Clinic B's source list is empty
    lst = await client.get("/api/v1/lead-capture/sources", headers=other_h)
    assert lst.status_code == 200 and lst.json() == []

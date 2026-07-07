import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.contact import Contact
from app.models.company import Company
from app.models.communication import CommunicationTemplate
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key): return storage.get(key)
    async def mock_set(key, value, ex=300): storage[key] = value; return True
    async def mock_delete(key): storage.pop(key, None); return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_features(*a, **k):
        return ["EMAIL_MESSAGING", "SMS_MESSAGING", "WHATSAPP_MESSAGING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Tpl Org", "slug": "tpl-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@tpl.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@tpl.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    contact = Contact(organization_id=org.id, first_name="Jane", last_name="Roe", email="jane@x.com",
                      phone="+15550001", created_by=admin.id)
    company = Company(organization_id=org.id, name="Acme", created_by=admin.id)
    db.add_all([contact, company])
    await db.commit()
    return {
        "org": org, "admin": admin, "emp": emp, "contact": contact, "company": company,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _mk(client, headers, **over):
    payload = {"name": "T", "channel": "Email", "subject": "Hi {{first_name}}",
               "body": "Hello {{full_name}} at {{company}} — {{owner}}", "category": "Sales"}
    payload.update(over)
    r = await client.post("/api/v1/templates", json=payload, headers=headers)
    return r


@pytest.mark.asyncio
async def test_create_defaults_to_draft_and_variables(client: AsyncClient, setup: dict):
    data = setup
    r = await _mk(client, data["h_emp"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "draft"
    assert r.json()["version"] == 1
    assert r.json()["category"] == "Sales"

    v = await client.get("/api/v1/templates/variables", headers=data["h_emp"])
    keys = {x["key"] for x in v.json()}
    assert {"first_name", "full_name", "company", "owner", "date"} <= keys


@pytest.mark.asyncio
async def test_call_script_channel(client: AsyncClient, setup: dict):
    data = setup
    r = await _mk(client, data["h_admin"], channel="Call", subject=None, body="Greeting: hello {{first_name}}")
    assert r.status_code == 201, r.text
    assert r.json()["channel"] == "Call"
    # invalid channel rejected
    r = await _mk(client, data["h_admin"], channel="Pigeon")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_approval_workflow_and_permissions(client: AsyncClient, setup: dict):
    data = setup
    tid = (await _mk(client, data["h_emp"])).json()["id"]

    # employee cannot approve
    assert (await client.post(f"/api/v1/templates/{tid}/approve", headers=data["h_emp"])).status_code == 403
    # cannot approve while draft
    assert (await client.post(f"/api/v1/templates/{tid}/approve", headers=data["h_admin"])).status_code == 400

    # submit → pending
    r = await client.post(f"/api/v1/templates/{tid}/submit", headers=data["h_emp"])
    assert r.status_code == 200
    assert r.json()["status"] == "pending_approval"

    # reject with reason
    r = await client.post(f"/api/v1/templates/{tid}/reject", json={"reason": "Tone"}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejected_reason"] == "Tone"

    # resubmit → approve
    await client.post(f"/api/v1/templates/{tid}/submit", headers=data["h_emp"])
    r = await client.post(f"/api/v1/templates/{tid}/approve", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["approved_by"] == str(data["admin"].id)


@pytest.mark.asyncio
async def test_version_history_and_restore(client: AsyncClient, setup: dict):
    data = setup
    tid = (await _mk(client, data["h_admin"], body="v1 body")).json()["id"]
    # edit twice → two snapshots (v1, v2), current becomes v3
    await client.patch(f"/api/v1/templates/{tid}", json={"body": "v2 body", "change_note": "tweak"}, headers=data["h_admin"])
    r = await client.patch(f"/api/v1/templates/{tid}", json={"body": "v3 body"}, headers=data["h_admin"])
    assert r.json()["version"] == 3

    versions = await client.get(f"/api/v1/templates/{tid}/versions", headers=data["h_admin"])
    assert {v["version"] for v in versions.json()} == {1, 2}
    assert any(v["body"] == "v1 body" for v in versions.json())

    # restore v1 → content reverts, version bumps to 4
    r = await client.post(f"/api/v1/templates/{tid}/versions/1/restore", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["body"] == "v1 body"
    assert r.json()["version"] == 4


@pytest.mark.asyncio
async def test_edit_resets_approved_to_draft(client: AsyncClient, setup: dict):
    data = setup
    tid = (await _mk(client, data["h_admin"])).json()["id"]
    await client.post(f"/api/v1/templates/{tid}/submit", headers=data["h_admin"])
    await client.post(f"/api/v1/templates/{tid}/approve", headers=data["h_admin"])
    r = await client.patch(f"/api/v1/templates/{tid}", json={"body": "changed"}, headers=data["h_admin"])
    assert r.json()["status"] == "draft"  # re-approval required
    assert r.json()["approved_by"] is None


@pytest.mark.asyncio
async def test_preview_sample_and_entity(client: AsyncClient, setup: dict):
    data = setup
    tid = (await _mk(client, data["h_admin"])).json()["id"]
    # sample data
    r = await client.post(f"/api/v1/templates/{tid}/preview", json={}, headers=data["h_admin"])
    assert r.status_code == 200
    assert "Jane Doe" in r.json()["body"] and "Acme Corp" in r.json()["body"]
    # real entity
    r = await client.post(f"/api/v1/templates/{tid}/preview", json={
        "contact_id": str(data["contact"].id), "company_id": str(data["company"].id)}, headers=data["h_admin"])
    assert r.json()["subject"] == "Hi Jane"
    assert "Jane Roe at Acme" in r.json()["body"]
    assert "Admin One" in r.json()["body"]


@pytest.mark.asyncio
async def test_test_send_email_and_call(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # Email test send → creates an outbound email + counts usage
    et = (await _mk(client, data["h_admin"], channel="Email")).json()["id"]
    r = await client.post(f"/api/v1/templates/{et}/test", json={"to": "me@here.com"}, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True and r.json()["channel"] == "Email"
    assert r.json()["activity_id"]

    # Call script test → returns preview, nothing transmitted
    ct = (await _mk(client, data["h_admin"], channel="Call", subject=None, body="Hi {{first_name}}")).json()["id"]
    r = await client.post(f"/api/v1/templates/{ct}/test", json={}, headers=data["h_admin"])
    assert r.json()["sent"] is False and r.json()["channel"] == "Call"
    assert "Jane" in r.json()["preview"]

    t = (await db.execute(select(CommunicationTemplate).filter(CommunicationTemplate.id == uuid.UUID(et)))).scalars().first()
    assert t.usage_count >= 1


@pytest.mark.asyncio
async def test_reports_and_categories(client: AsyncClient, setup: dict):
    data = setup
    await _mk(client, data["h_admin"], name="A", channel="Email", category="Sales")
    await _mk(client, data["h_admin"], name="B", channel="SMS", category="Support")
    await _mk(client, data["h_admin"], name="C", channel="Call", category="Sales")

    cats = await client.get("/api/v1/templates/categories", headers=data["h_admin"])
    assert set(cats.json()) == {"Sales", "Support"}

    r = await client.get("/api/v1/templates/reports", headers=data["h_admin"])
    assert r.status_code == 200
    rep = r.json()
    assert rep["total"] == 3
    assert rep["drafts"] == 3
    ch = {b["label"]: b["count"] for b in rep["by_channel"]}
    assert ch == {"Email": 1, "SMS": 1, "Call": 1}
    cat = {b["label"]: b["count"] for b in rep["by_category"]}
    assert cat["Sales"] == 2


@pytest.mark.asyncio
async def test_list_filters(client: AsyncClient, setup: dict):
    data = setup
    await _mk(client, data["h_admin"], name="E1", channel="Email")
    await _mk(client, data["h_admin"], name="S1", channel="SMS")
    r = await client.get("/api/v1/templates", params={"channel": "SMS"}, headers=data["h_admin"])
    assert all(t["channel"] == "SMS" for t in r.json())
    r = await client.get("/api/v1/templates", params={"status": "draft"}, headers=data["h_admin"])
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_legacy_list_only_shows_approved(client: AsyncClient, setup: dict):
    data = setup
    # a draft created via the managed module is NOT offered to composers
    draft = (await _mk(client, data["h_admin"], name="DraftOnly")).json()["id"]
    legacy = await client.get("/api/v1/communications/templates", headers=data["h_admin"])
    assert not any(t["id"] == draft for t in legacy.json())

    # approve it → now it appears for composers
    await client.post(f"/api/v1/templates/{draft}/submit", headers=data["h_admin"])
    await client.post(f"/api/v1/templates/{draft}/approve", headers=data["h_admin"])
    legacy = await client.get("/api/v1/communications/templates", headers=data["h_admin"])
    assert any(t["id"] == draft for t in legacy.json())


@pytest.mark.asyncio
async def test_delete_permissions(client: AsyncClient, setup: dict):
    data = setup
    # emp creates; another employee-less scenario — admin can delete anyone's, emp only own
    tid = (await _mk(client, data["h_emp"])).json()["id"]
    # admin (privileged) can delete emp's template
    assert (await client.delete(f"/api/v1/templates/{tid}", headers=data["h_admin"])).status_code == 204

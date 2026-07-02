import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.contact import Contact
from app.models.company import Company


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Comm Org", "slug": "comm-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@comm.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@comm.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True})
    await db.commit()
    contact = Contact(organization_id=org.id, first_name="Jane", last_name="Roe", email="jane@x.com", created_by=admin.id)
    company = Company(organization_id=org.id, name="Acme", created_by=admin.id)
    db.add_all([contact, company])
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "contact": contact, "company": company,
            "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "emp_headers": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_log_channels_and_feed(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    for ch in ["Call", "SMS", "WhatsApp", "Email"]:
        r = await client.post("/api/v1/communications/", json={
            "channel": ch, "direction": "OUTBOUND", "subject": f"{ch} msg", "body": f"hi via {ch}", "contact_id": cid}, headers=data["headers"])
        assert r.status_code == 201, r.text
    # internal note
    r = await client.post("/api/v1/communications/", json={"channel": "Note", "subject": "n", "body": "internal note", "contact_id": cid}, headers=data["headers"])
    assert r.status_code == 201
    assert r.json()["internal"] is True

    feed = await client.get("/api/v1/communications/", params={"contact_id": cid}, headers=data["headers"])
    channels = {i["channel"] for i in feed.json()}
    assert {"Call", "SMS", "WhatsApp", "Email", "Note"} <= channels

    # channel filter
    onlysms = await client.get("/api/v1/communications/", params={"contact_id": cid, "channel": "SMS"}, headers=data["headers"])
    assert all(i["channel"] == "SMS" for i in onlysms.json())
    # search
    srch = await client.get("/api/v1/communications/", params={"contact_id": cid, "search": "WhatsApp"}, headers=data["headers"])
    assert any("WhatsApp" in i["subject"] for i in srch.json())


@pytest.mark.asyncio
async def test_log_requires_link(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/communications/", json={"channel": "SMS", "subject": "orphan"}, headers=data["headers"])
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_unread_read_and_conversations(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    # inbound message = unread
    inb = await client.post("/api/v1/communications/", json={"channel": "SMS", "direction": "INBOUND", "subject": "inbound", "contact_id": cid}, headers=data["headers"])
    aid = inb.json()["id"]
    assert inb.json()["is_read"] is False

    unread = await client.get("/api/v1/communications/", params={"contact_id": cid, "unread_only": True}, headers=data["headers"])
    assert any(i["id"] == aid for i in unread.json())

    convos = await client.get("/api/v1/communications/conversations", headers=data["headers"])
    conv = next(c for c in convos.json() if c["entity_id"] == cid)
    assert conv["unread_count"] >= 1
    assert conv["name"] == "Jane Roe"

    # mark read
    await client.post(f"/api/v1/communications/{aid}/read", headers=data["headers"])
    unread2 = await client.get("/api/v1/communications/", params={"contact_id": cid, "unread_only": True}, headers=data["headers"])
    assert not any(i["id"] == aid for i in unread2.json())


@pytest.mark.asyncio
async def test_pin(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    m = await client.post("/api/v1/communications/", json={"channel": "Email", "subject": "pin me", "contact_id": cid}, headers=data["headers"])
    aid = m.json()["id"]
    p = await client.post(f"/api/v1/communications/{aid}/pin", headers=data["headers"])
    assert p.json()["pinned"] is True
    pinned = await client.get("/api/v1/communications/", params={"contact_id": cid, "pinned_only": True}, headers=data["headers"])
    assert any(i["id"] == aid and i["is_pinned"] for i in pinned.json())


@pytest.mark.asyncio
async def test_stats(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    await client.post("/api/v1/communications/", json={"channel": "Call", "direction": "OUTBOUND", "subject": "a", "contact_id": cid}, headers=data["headers"])
    await client.post("/api/v1/communications/", json={"channel": "SMS", "direction": "INBOUND", "subject": "b", "contact_id": cid}, headers=data["headers"])
    s = await client.get("/api/v1/communications/stats", headers=data["headers"])
    assert s.status_code == 200
    body = s.json()
    assert body["total"] == 2
    assert body["unread"] == 1
    assert any(c["label"] == "Call" for c in body["by_channel"])


@pytest.mark.asyncio
async def test_templates_and_render(client: AsyncClient, setup: dict):
    data = setup
    t = await client.post("/api/v1/communications/templates", json={
        "name": "Welcome", "channel": "Email", "subject": "Hi {{first_name}}",
        "body": "Hello {{full_name}} from {{company}}. — {{owner}}"}, headers=data["headers"])
    assert t.status_code == 201
    tid = t.json()["id"]
    r = await client.post(f"/api/v1/communications/templates/{tid}/render", json={
        "contact_id": str(data["contact"].id), "company_id": str(data["company"].id)}, headers=data["headers"])
    assert r.status_code == 200
    assert r.json()["subject"] == "Hi Jane"
    assert "Jane Roe from Acme" in r.json()["body"]
    assert "Admin One" in r.json()["body"]

    lst = await client.get("/api/v1/communications/templates", headers=data["headers"])
    assert any(x["id"] == tid for x in lst.json())
    await client.delete(f"/api/v1/communications/templates/{tid}", headers=data["headers"])


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.asyncio
async def test_attachments(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    m = await client.post("/api/v1/communications/", json={"channel": "Email", "subject": "with file", "contact_id": cid}, headers=data["headers"])
    aid = m.json()["id"]
    up = await client.post(f"/api/v1/communications/{aid}/attachments", files={"file": ("a.png", PNG, "image/png")}, headers=data["headers"])
    assert up.status_code == 201
    lst = await client.get(f"/api/v1/communications/{aid}/attachments", headers=data["headers"])
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_scoping(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contact"].id)
    # admin logs a comm (assigned to admin)
    await client.post("/api/v1/communications/", json={"channel": "SMS", "subject": "admin only", "contact_id": cid}, headers=data["headers"])
    feed = await client.get("/api/v1/communications/", params={"contact_id": cid}, headers=data["emp_headers"])
    assert not any(i["subject"] == "admin only" for i in feed.json())

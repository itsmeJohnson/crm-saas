import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.contact import Contact
from app.models.company import Company
from app.models.activity import Activity
from app.models.notification import Notification


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Contact Org", "slug": "contact-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@c.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True,
    })
    rep = await user_repo.create_user(org.id, {
        "email": "rep@c.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Rep", "last_name": "Two", "role": "Employee", "is_active": True,
    })
    await db.commit()

    company = Company(organization_id=org.id, name="Acme Corp", created_by=admin.id)
    db.add(company)
    await db.commit()

    contacts = []
    for i in range(3):
        c = Contact(
            organization_id=org.id, first_name=f"Con{i}", last_name="Tact",
            email=f"con{i}@acme.com", phone=f"+1555000{i}",
            job_title="Manager" if i < 2 else "CEO",
            company_id=company.id if i == 0 else None,
            assigned_user_id=admin.id, created_by=admin.id,
            tags=["lead"] if i == 0 else None,
        )
        db.add(c)
        contacts.append(c)
    await db.commit()

    return {
        "org": org, "admin": admin, "rep": rep, "company": company, "contacts": contacts,
        "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
    }


# --- Tranche A ---

@pytest.mark.asyncio
async def test_create_contact_with_tags_and_notify(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    payload = {"first_name": "New", "last_name": "Person", "tags": ["hot", "vip"],
               "assigned_user_id": str(data["rep"].id)}
    res = await client.post("/api/v1/contacts/", json=payload, headers=data["headers"])
    assert res.status_code == 201
    assert set(res.json()["tags"]) == {"hot", "vip"}
    # rep should get an assignment notification
    n = await db.execute(select(Notification).filter(
        Notification.user_id == data["rep"].id, Notification.category == "contact"))
    assert n.scalars().first() is not None


@pytest.mark.asyncio
async def test_export_contacts_csv(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/contacts/export?format=csv", headers=data["headers"])
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "first_name" in res.text
    assert res.text.strip().count("\n") == 3  # header + 3


@pytest.mark.asyncio
async def test_import_contacts_csv(client: AsyncClient, setup: dict):
    data = setup
    csv_bytes = b"first_name,last_name,email,job_title,company\nJane,Doe,jane@x.com,VP,NewCo\n,Missing,bad@x.com,,\n"
    files = {"file": ("import.csv", csv_bytes, "text/csv")}
    res = await client.post("/api/v1/contacts/import", files=files, headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 1
    assert body["failed"] == 1


@pytest.mark.asyncio
async def test_duplicate_detection(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/contacts/duplicates?email=con0@acme.com", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_filters_tag_and_has_email(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    res = await client.get("/api/v1/contacts/?tag=lead", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) == 1

    # contact with no email
    c = Contact(organization_id=data["org"].id, first_name="No", last_name="Email", created_by=data["admin"].id)
    db.add(c)
    await db.commit()
    res = await client.get("/api/v1/contacts/?has_email=false", headers=data["headers"])
    assert all(not r["email"] for r in res.json())
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_bulk_update_and_delete(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    ids = [str(c.id) for c in data["contacts"]]
    res = await client.post("/api/v1/contacts/bulk-update", json={
        "contact_ids": ids, "fields": {"add_tags": ["batch"], "assigned_user_id": str(data["rep"].id)},
    }, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["affected_count"] == 3

    db_res = await db.execute(select(Contact).filter(Contact.id.in_([uuid.UUID(i) for i in ids])))
    for c in db_res.scalars().all():
        assert "batch" in (c.tags or [])
        assert c.assigned_user_id == data["rep"].id

    res = await client.post("/api/v1/contacts/bulk-delete", json={"contact_ids": ids[:2]}, headers=data["headers"])
    assert res.json()["affected_count"] == 2
    res = await client.get("/api/v1/contacts/", headers=data["headers"])
    remaining = [r["id"] for r in res.json()]
    assert ids[0] not in remaining


# --- Tranche B ---

@pytest.mark.asyncio
async def test_custom_field_definition_and_validation(client: AsyncClient, setup: dict):
    data = setup
    # unknown custom field rejected
    bad = await client.post("/api/v1/contacts/", json={
        "first_name": "X", "last_name": "Y", "custom_fields": {"loyalty": "gold"}}, headers=data["headers"])
    assert bad.status_code == 400

    # define it
    d = await client.post("/api/v1/contacts/custom-fields", json={
        "key": "loyalty", "label": "Loyalty Tier", "field_type": "select", "options": ["gold", "silver"]},
        headers=data["headers"])
    assert d.status_code == 201

    # now accepted
    ok = await client.post("/api/v1/contacts/", json={
        "first_name": "X", "last_name": "Y", "custom_fields": {"loyalty": "gold"}}, headers=data["headers"])
    assert ok.status_code == 201
    assert ok.json()["custom_fields"] == {"loyalty": "gold"}

    lst = await client.get("/api/v1/contacts/custom-fields", headers=data["headers"])
    assert any(f["key"] == "loyalty" for f in lst.json())


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_attachments(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["contacts"][0].id)
    files = {"file": ("doc.png", PNG_BYTES, "image/png")}
    res = await client.post(f"/api/v1/contacts/{cid}/attachments", files=files, headers=data["headers"])
    assert res.status_code == 201
    res = await client.get(f"/api/v1/contacts/{cid}/attachments", headers=data["headers"])
    assert len(res.json()) == 1
    fname = res.json()[0]["filename"]
    res = await client.request("DELETE", f"/api/v1/contacts/{cid}/attachments/{fname}", headers=data["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_timeline_and_communications(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    cid = data["contacts"][0].id
    # a call activity
    db.add(Activity(organization_id=data["org"].id, activity_type="Call", subject="Intro call",
                    status="Completed", contact_id=cid, created_by=data["admin"].id, call_direction="OUTBOUND"))
    await db.commit()
    # generate audit via update
    await client.patch(f"/api/v1/contacts/{cid}", json={"job_title": "Director"}, headers=data["headers"])
    await client.post("/api/v1/notes/", json={"content": "Met at conf", "contact_id": str(cid)}, headers=data["headers"])

    tl = await client.get(f"/api/v1/contacts/{cid}/timeline", headers=data["headers"])
    assert tl.status_code == 200
    types = {e["type"] for e in tl.json()}
    assert {"note", "activity", "audit"} <= types

    comm = await client.get(f"/api/v1/contacts/{cid}/communications", headers=data["headers"])
    assert comm.status_code == 200
    assert len(comm.json()) == 1
    assert comm.json()[0]["channel"] == "Call"


@pytest.mark.asyncio
async def test_tags_list(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/contacts/tags", headers=data["headers"])
    assert res.status_code == 200
    assert "lead" in res.json()


# --- Tranche C ---

@pytest.mark.asyncio
async def test_contact_report(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/contacts/reports", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["total_contacts"] == 3
    assert body["with_email"] == 3
    assert body["with_company"] == 1
    assert any(b["label"] == "Acme Corp" for b in body["by_company"])


# --- Tranche D ---

@pytest.mark.asyncio
async def test_merge_contacts(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    primary = data["contacts"][1]   # has no company, email con1
    secondary = data["contacts"][0]  # has company + tag "lead"
    # give secondary a note to re-point
    await client.post("/api/v1/notes/", json={"content": "note on secondary", "contact_id": str(secondary.id)}, headers=data["headers"])

    res = await client.post("/api/v1/contacts/merge", json={
        "primary_id": str(primary.id), "secondary_id": str(secondary.id)}, headers=data["headers"])
    assert res.status_code == 200
    merged = res.json()
    # primary had no company; filled from secondary
    assert merged["company_id"] == str(data["company"].id)
    assert "lead" in (merged["tags"] or [])

    # secondary is gone from listing
    lst = await client.get("/api/v1/contacts/", headers=data["headers"])
    assert str(secondary.id) not in [r["id"] for r in lst.json()]


@pytest.mark.asyncio
async def test_relationships(client: AsyncClient, setup: dict):
    data = setup
    a, b = str(data["contacts"][0].id), str(data["contacts"][1].id)
    res = await client.post(f"/api/v1/contacts/{a}/relationships", json={
        "related_contact_id": b, "relationship_type": "reports_to"}, headers=data["headers"])
    assert res.status_code == 201
    rid = res.json()["id"]
    assert res.json()["related_contact_name"] == "Con1 Tact"

    lst = await client.get(f"/api/v1/contacts/{a}/relationships", headers=data["headers"])
    assert len(lst.json()) == 1

    res = await client.request("DELETE", f"/api/v1/contacts/{a}/relationships/{rid}", headers=data["headers"])
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_contact_workflow_fires(client: AsyncClient, setup: dict):
    data = setup
    # rule: on contact_created, if job_title == CEO -> add_tag "executive"
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Tag execs", "trigger_event": "contact_created",
        "conditions": [{"field": "job_title", "op": "eq", "value": "CEO"}],
        "actions": [{"type": "add_tag", "value": "executive"}],
    }, headers=data["headers"])
    assert r.status_code == 201

    res = await client.post("/api/v1/contacts/", json={
        "first_name": "Big", "last_name": "Boss", "job_title": "CEO"}, headers=data["headers"])
    assert res.status_code == 201
    assert "executive" in (res.json()["tags"] or [])

    # non-CEO unaffected
    res2 = await client.post("/api/v1/contacts/", json={
        "first_name": "Reg", "last_name": "Ular", "job_title": "Analyst"}, headers=data["headers"])
    assert "executive" not in (res2.json()["tags"] or [])

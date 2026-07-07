import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.pipeline import PipelineStage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "TL Org", "slug": "tl-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@tl.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True,
    })
    await db.commit()
    customer = Company(organization_id=org.id, name="Timeline Co", company_type="Customer", created_by=admin.id)
    db.add(customer)
    await db.commit()
    # a contact + activity (call) on it
    contact = Contact(organization_id=org.id, first_name="Jane", last_name="Doe", company_id=customer.id, created_by=admin.id)
    db.add(contact)
    await db.commit()
    db.add(Activity(organization_id=org.id, activity_type="Call", subject="Intro", status="Completed",
                    contact_id=contact.id, created_by=admin.id, call_direction="OUTBOUND"))
    stage = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalar()
    db.add(Lead(organization_id=org.id, last_name="L", title="Deal", company_id=customer.id,
                company_name="Timeline Co", value=1000, created_by=admin.id, stage_id=stage))
    await db.commit()
    return {"org": org, "admin": admin, "customer": customer, "contact": contact,
            "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"}}


@pytest.mark.asyncio
async def test_unified_timeline_aggregates_all_sources(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["customer"].id)
    # add a note, an order, an invoice, a payment
    await client.post("/api/v1/notes/", json={"content": "Kickoff done", "company_id": cid}, headers=data["headers"])
    order = (await client.post("/api/v1/customers/orders", json={
        "company_id": cid, "items": [{"description": "X", "quantity": 1, "unit_price": 500}]}, headers=data["headers"])).json()
    inv = (await client.post("/api/v1/customers/invoices/from-order", json={"order_id": order["id"]}, headers=data["headers"])).json()
    await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments", json={"amount": 200}, headers=data["headers"])

    res = await client.get(f"/api/v1/customers/{cid}/timeline", headers=data["headers"])
    assert res.status_code == 200
    events = res.json()
    types = {e["type"] for e in events}
    # activity(call), note, order, invoice, payment all present
    assert "call" in types
    assert "note" in types
    assert "order" in types
    assert "invoice" in types
    assert "payment" in types
    # each event has a group (day) + sorted desc
    assert all("group" in e for e in events)
    ts = [e["timestamp"] for e in events]
    assert ts == sorted(ts, reverse=True)


@pytest.mark.asyncio
async def test_timeline_type_filter_and_search(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["customer"].id)
    await client.post("/api/v1/notes/", json={"content": "Special note ABC", "company_id": cid}, headers=data["headers"])

    # type filter
    res = await client.get(f"/api/v1/customers/{cid}/timeline?types=note", headers=data["headers"])
    assert res.status_code == 200
    assert all(e["type"] == "note" for e in res.json())
    assert len(res.json()) >= 1

    # search
    res = await client.get(f"/api/v1/customers/{cid}/timeline?search=ABC", headers=data["headers"])
    assert any("ABC" in (e["description"] or "") for e in res.json())


@pytest.mark.asyncio
async def test_timeline_export_csv(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["customer"].id)
    res = await client.get(f"/api/v1/customers/{cid}/timeline/export", headers=data["headers"])
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "date,type,source,title" in res.text


@pytest.mark.asyncio
async def test_workflow_events_appear_in_timeline(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    cid = str(data["customer"].id)
    # rule: on lead_created if value >= 100 -> set priority High
    await client.post("/api/v1/leads/workflows", json={
        "name": "High value", "trigger_event": "lead_created",
        "conditions": [{"field": "value", "op": "gte", "value": 100}],
        "actions": [{"type": "set_priority", "value": "High"}],
    }, headers=data["headers"])
    # create a lead linked to this customer
    await client.post("/api/v1/leads/", json={
        "last_name": "WF", "title": "WF Deal", "company_name": "Timeline Co", "value": 5000}, headers=data["headers"])

    res = await client.get(f"/api/v1/customers/{cid}/timeline?types=workflow", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["type"] == "workflow"

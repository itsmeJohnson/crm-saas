import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.company import Company
from app.models.customer_invoice import CustomerInvoice
from app.models.notification import Notification


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Cust Org", "slug": "cust-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@cust.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True,
    })
    rep = await user_repo.create_user(org.id, {
        "email": "rep@cust.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Rep", "last_name": "Two", "role": "Employee", "is_active": True,
    })
    await db.commit()
    customer = Company(organization_id=org.id, name="BigCo", company_type="Customer",
                       assigned_user_id=rep.id, created_by=admin.id)
    db.add(customer)
    await db.commit()
    return {
        "org": org, "admin": admin, "rep": rep, "customer": customer,
        "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
    }


ITEMS = [{"description": "Widget", "quantity": 2, "unit_price": 100}, {"description": "Setup", "quantity": 1, "unit_price": 50}]


@pytest.mark.asyncio
async def test_order_crud_and_totals(client: AsyncClient, setup: dict):
    data = setup
    res = await client.post("/api/v1/customers/orders", json={
        "company_id": str(data["customer"].id), "items": ITEMS, "tax_amount": 25, "discount_amount": 10,
    }, headers=data["headers"])
    assert res.status_code == 201
    body = res.json()
    assert body["order_number"].startswith("ORD-")
    assert float(body["subtotal"]) == 250.0        # 2*100 + 1*50
    assert float(body["total_amount"]) == 265.0     # 250 + 25 - 10
    oid = body["id"]

    # update status
    res = await client.patch(f"/api/v1/customers/orders/{oid}", json={"status": "Confirmed"}, headers=data["headers"])
    assert res.json()["status"] == "Confirmed"

    res = await client.get("/api/v1/customers/orders", headers=data["headers"])
    assert any(o["id"] == oid for o in res.json())


@pytest.mark.asyncio
async def test_invoice_from_order_and_pdf(client: AsyncClient, setup: dict):
    data = setup
    order = (await client.post("/api/v1/customers/orders", json={
        "company_id": str(data["customer"].id), "items": ITEMS}, headers=data["headers"])).json()
    inv = await client.post("/api/v1/customers/invoices/from-order", json={"order_id": order["id"]}, headers=data["headers"])
    assert inv.status_code == 201
    body = inv.json()
    assert body["order_id"] == order["id"]
    assert float(body["total_amount"]) == 250.0
    assert float(body["balance_due"]) == 250.0
    iid = body["id"]

    # send
    sent = await client.post(f"/api/v1/customers/invoices/{iid}/send", headers=data["headers"])
    assert sent.json()["status"] == "Sent"

    # pdf
    pdf = await client.get(f"/api/v1/customers/invoices/{iid}/pdf", headers=data["headers"])
    assert pdf.status_code == 200
    assert pdf.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_payment_updates_balance_and_status(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    inv = (await client.post("/api/v1/customers/invoices", json={
        "company_id": str(data["customer"].id), "items": ITEMS}, headers=data["headers"])).json()
    iid = inv["id"]
    assert float(inv["total_amount"]) == 250.0

    # partial payment
    p1 = await client.post(f"/api/v1/customers/invoices/{iid}/payments", json={"amount": 100, "method": "UPI"}, headers=data["headers"])
    assert p1.status_code == 201
    got = (await client.get(f"/api/v1/customers/invoices/{iid}", headers=data["headers"])).json()
    assert float(got["amount_paid"]) == 100.0
    assert float(got["balance_due"]) == 150.0
    assert got["status"] == "PartiallyPaid"

    # full payment
    await client.post(f"/api/v1/customers/invoices/{iid}/payments", json={"amount": 150}, headers=data["headers"])
    got = (await client.get(f"/api/v1/customers/invoices/{iid}", headers=data["headers"])).json()
    assert float(got["balance_due"]) == 0.0
    assert got["status"] == "Paid"

    # owner (rep) notified
    n = await db.execute(select(Notification).filter(Notification.user_id == data["rep"].id, Notification.category == "payment"))
    assert n.scalars().first() is not None


@pytest.mark.asyncio
async def test_contract_crud(client: AsyncClient, setup: dict):
    data = setup
    res = await client.post("/api/v1/customers/contracts", json={
        "company_id": str(data["customer"].id), "title": "MSA 2026", "status": "Active",
        "value": 120000, "start_date": "2026-01-01", "end_date": "2026-12-31",
    }, headers=data["headers"])
    assert res.status_code == 201
    assert res.json()["contract_number"].startswith("CTR-")
    cid = res.json()["id"]
    res = await client.patch(f"/api/v1/customers/contracts/{cid}", json={"status": "Renewed"}, headers=data["headers"])
    assert res.json()["status"] == "Renewed"
    res = await client.get("/api/v1/customers/contracts?status=Renewed", headers=data["headers"])
    assert any(c["id"] == cid for c in res.json())


@pytest.mark.asyncio
async def test_customer_list_and_summary(client: AsyncClient, setup: dict):
    data = setup
    cust_id = str(data["customer"].id)
    await client.post("/api/v1/customers/orders", json={"company_id": cust_id, "items": ITEMS}, headers=data["headers"])
    inv = (await client.post("/api/v1/customers/invoices", json={"company_id": cust_id, "items": ITEMS}, headers=data["headers"])).json()
    await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments", json={"amount": 100}, headers=data["headers"])

    lst = await client.get("/api/v1/customers/", headers=data["headers"])
    assert lst.status_code == 200
    row = next(c for c in lst.json() if c["company_id"] == cust_id)
    assert row["order_count"] == 1
    assert row["total_invoiced"] == 250.0
    assert row["outstanding_balance"] == 150.0

    summ = await client.get(f"/api/v1/customers/{cust_id}/summary", headers=data["headers"])
    assert summ.status_code == 200
    s = summ.json()
    assert s["orders"]["count"] == 1
    assert s["invoices"]["outstanding"] == 150.0
    assert s["payments"]["total_collected"] == 100.0


@pytest.mark.asyncio
async def test_dunning_marks_overdue(client: AsyncClient, db: AsyncSession, setup: dict):
    from app.cron.customer_cron import mark_overdue_invoices
    data = setup
    cust_id = str(data["customer"].id)
    # invoice due yesterday, sent
    inv = (await client.post("/api/v1/customers/invoices", json={
        "company_id": cust_id, "items": ITEMS,
        "due_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }, headers=data["headers"])).json()
    await client.post(f"/api/v1/customers/invoices/{inv['id']}/send", headers=data["headers"])

    count = await mark_overdue_invoices(db)
    await db.commit()
    assert count == 1
    got = (await client.get(f"/api/v1/customers/invoices/{inv['id']}", headers=data["headers"])).json()
    assert got["status"] == "Overdue"


@pytest.mark.asyncio
async def test_reports(client: AsyncClient, setup: dict):
    data = setup
    cust_id = str(data["customer"].id)
    await client.post("/api/v1/customers/orders", json={"company_id": cust_id, "items": ITEMS}, headers=data["headers"])
    inv = (await client.post("/api/v1/customers/invoices", json={"company_id": cust_id, "items": ITEMS}, headers=data["headers"])).json()
    await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments", json={"amount": 200}, headers=data["headers"])

    res = await client.get("/api/v1/customers/reports", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["total_customers"] == 1
    assert body["total_orders"] == 1
    assert body["total_invoiced"] == 250.0
    assert body["total_collected"] == 200.0
    assert body["outstanding_ar"] == 50.0
    assert any(t["name"] == "BigCo" for t in body["top_customers"])


@pytest.mark.asyncio
async def test_order_for_foreign_company_rejected(client: AsyncClient, setup: dict):
    data = setup
    res = await client.post("/api/v1/customers/orders", json={
        "company_id": str(uuid.uuid4()), "items": ITEMS}, headers=data["headers"])
    assert res.status_code == 400

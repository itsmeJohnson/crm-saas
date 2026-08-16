"""Regression tests for the QA-audit findings (2026-08-10).

Covers:
  BUG-001  invoice overpayment must be rejected (no negative balance)
  BUG-002  Employee role can do clinical/billing WORK but not destructive/admin ops
  BUG-003  overlapping appointments for the same assignee are rejected
  BUG-004  duplicate patient (same phone/email) is rejected on create
Each fix ships with an explicit override flag; both paths are asserted.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.company import Company


@pytest.fixture
async def env(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Regress Org", "slug": "regress-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@regress.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True,
    })
    employee = await user_repo.create_user(org.id, {
        "email": "doc@regress.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Deepa", "last_name": "Dentist", "role": "Employee", "is_active": True,
    })
    await db.commit()
    company = Company(organization_id=org.id, name="Patient Family", company_type="Customer",
                      created_by=admin.id)
    db.add(company)
    await db.commit()
    return {
        "org": org, "admin": admin, "employee": employee, "company": company,
        "admin_h": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "emp_h": {"Authorization": f"Bearer {create_access_token(employee.id)}"},
    }


def _invoice_payload(company_id, unit_price):
    return {"company_id": str(company_id), "currency": "INR",
            "items": [{"description": "Treatment", "quantity": 1, "unit_price": unit_price}]}


async def _make_invoice(client, env, unit_price):
    res = await client.post("/api/v1/customers/invoices",
                            json=_invoice_payload(env["company"].id, unit_price), headers=env["admin_h"])
    assert res.status_code == 201, res.text
    return res.json()


# ============================ BUG-001: overpayment ============================
@pytest.mark.asyncio
async def test_overpayment_rejected(client: AsyncClient, env: dict):
    inv = await _make_invoice(client, env, 1000)
    res = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                            json={"amount": 5000, "method": "Cash"}, headers=env["admin_h"])
    assert res.status_code == 400, res.text
    # invoice must be untouched
    got = (await client.get(f"/api/v1/customers/invoices/{inv['id']}", headers=env["admin_h"])).json()
    assert float(got["amount_paid"]) == 0.0
    assert float(got["balance_due"]) == 1000.0


@pytest.mark.asyncio
async def test_partial_then_exact_payment_never_negative(client: AsyncClient, env: dict):
    inv = await _make_invoice(client, env, 1000)
    p1 = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                           json={"amount": 600, "method": "UPI"}, headers=env["admin_h"])
    assert p1.status_code == 201
    mid = (await client.get(f"/api/v1/customers/invoices/{inv['id']}", headers=env["admin_h"])).json()
    assert float(mid["balance_due"]) == 400.0 and mid["status"] == "PartiallyPaid"
    # overshoot the remaining 400 -> rejected
    over = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                             json={"amount": 500, "method": "Cash"}, headers=env["admin_h"])
    assert over.status_code == 400
    # exact remainder -> paid, zero balance
    p2 = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                           json={"amount": 400, "method": "Cash"}, headers=env["admin_h"])
    assert p2.status_code == 201
    done = (await client.get(f"/api/v1/customers/invoices/{inv['id']}", headers=env["admin_h"])).json()
    assert float(done["balance_due"]) == 0.0 and done["status"] == "Paid"
    # any further payment on a settled invoice -> rejected
    extra = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                              json={"amount": 1, "method": "Cash"}, headers=env["admin_h"])
    assert extra.status_code == 400


@pytest.mark.asyncio
async def test_overpayment_allowed_with_flag(client: AsyncClient, env: dict):
    inv = await _make_invoice(client, env, 1000)
    res = await client.post(f"/api/v1/customers/invoices/{inv['id']}/payments",
                            json={"amount": 1500, "method": "Cash", "allow_overpayment": True}, headers=env["admin_h"])
    assert res.status_code == 201, res.text
    got = (await client.get(f"/api/v1/customers/invoices/{inv['id']}", headers=env["admin_h"])).json()
    assert float(got["amount_paid"]) == 1500.0
    assert float(got["balance_due"]) == -500.0  # advance/credit, only via explicit opt-in


# ============================ BUG-002: Employee RBAC ============================
@pytest.mark.asyncio
async def test_employee_can_do_clinical_and_billing_work(client: AsyncClient, env: dict):
    # view + create patients
    assert (await client.get("/api/v1/contacts/", headers=env["emp_h"])).status_code == 200
    made = await client.post("/api/v1/contacts/",
                             json={"first_name": "Riya", "last_name": "Patient", "phone": "+919000000001"},
                             headers=env["emp_h"])
    assert made.status_code == 201, made.text
    # view + create invoices, record payment
    assert (await client.get("/api/v1/customers/invoices", headers=env["emp_h"])).status_code == 200
    inv = await client.post("/api/v1/customers/invoices",
                            json=_invoice_payload(env["company"].id, 500), headers=env["emp_h"])
    assert inv.status_code == 201, inv.text
    pay = await client.post(f"/api/v1/customers/invoices/{inv.json()['id']}/payments",
                            json={"amount": 500, "method": "Cash"}, headers=env["emp_h"])
    assert pay.status_code == 201


@pytest.mark.asyncio
async def test_employee_cannot_destroy(client: AsyncClient, env: dict):
    inv = await _make_invoice(client, env, 1000)
    # delete invoice -> forbidden for Employee, allowed for admin
    assert (await client.delete(f"/api/v1/customers/invoices/{inv['id']}", headers=env["emp_h"])).status_code == 403
    # void invoice -> forbidden for Employee
    voided = await client.patch(f"/api/v1/customers/invoices/{inv['id']}",
                                json={"status": "Void"}, headers=env["emp_h"])
    assert voided.status_code == 403, voided.text
    # admin can void
    ok = await client.patch(f"/api/v1/customers/invoices/{inv['id']}",
                            json={"status": "Void"}, headers=env["admin_h"])
    assert ok.status_code == 200 and ok.json()["status"] == "Void"


@pytest.mark.asyncio
async def test_employee_cannot_delete_patient(client: AsyncClient, env: dict):
    made = (await client.post("/api/v1/contacts/",
            json={"first_name": "Temp", "last_name": "Patient", "phone": "+919000000002"},
            headers=env["admin_h"])).json()
    assert (await client.delete(f"/api/v1/contacts/{made['id']}", headers=env["emp_h"])).status_code == 403
    assert (await client.delete(f"/api/v1/contacts/{made['id']}", headers=env["admin_h"])).status_code in (200, 204)


# ============================ BUG-003: double-booking ============================
def _appt(day_offset, h1, h2, title="Consult", etype="Appointment"):
    now = datetime.now(timezone.utc)
    return {"title": title, "event_type": etype,
            "start_at": (now + timedelta(days=day_offset, hours=h1)).isoformat(),
            "end_at": (now + timedelta(days=day_offset, hours=h2)).isoformat()}


@pytest.mark.asyncio
async def test_overlapping_appointment_rejected(client: AsyncClient, env: dict):
    a = await client.post("/api/v1/calendar/events", json=_appt(1, 10, 11), headers=env["admin_h"])
    assert a.status_code == 201
    # overlapping slot for same (default) assignee -> 409
    b = await client.post("/api/v1/calendar/events", json=_appt(1, 10, 11, title="Overlap"), headers=env["admin_h"])
    assert b.status_code == 409, b.text
    # non-overlapping slot -> ok
    c = await client.post("/api/v1/calendar/events", json=_appt(1, 11, 12, title="Later"), headers=env["admin_h"])
    assert c.status_code == 201


@pytest.mark.asyncio
async def test_overlapping_appointment_allowed_with_flag(client: AsyncClient, env: dict):
    await client.post("/api/v1/calendar/events", json=_appt(2, 9, 10), headers=env["admin_h"])
    dbl = await client.post("/api/v1/calendar/events",
                            json={**_appt(2, 9, 10, title="Double"), "allow_conflict": True}, headers=env["admin_h"])
    assert dbl.status_code == 201, dbl.text


@pytest.mark.asyncio
async def test_non_appointment_events_do_not_conflict(client: AsyncClient, env: dict):
    await client.post("/api/v1/calendar/events", json=_appt(3, 14, 15, title="M1", etype="Meeting"), headers=env["admin_h"])
    m2 = await client.post("/api/v1/calendar/events", json=_appt(3, 14, 15, title="M2", etype="Meeting"), headers=env["admin_h"])
    assert m2.status_code == 201  # meetings may overlap freely


# ============================ BUG-004: duplicate patient ============================
@pytest.mark.asyncio
async def test_duplicate_patient_rejected(client: AsyncClient, env: dict):
    first = await client.post("/api/v1/contacts/",
                              json={"first_name": "Sam", "last_name": "One", "phone": "+919111111111"},
                              headers=env["admin_h"])
    assert first.status_code == 201
    dup = await client.post("/api/v1/contacts/",
                            json={"first_name": "Sammy", "last_name": "Two", "phone": "+919111111111"},
                            headers=env["admin_h"])
    assert dup.status_code == 409, dup.text
    assert dup.json()["detail"]["existing_id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient, env: dict):
    await client.post("/api/v1/contacts/",
                      json={"first_name": "Mia", "last_name": "A", "email": "shared@fam.com"},
                      headers=env["admin_h"])
    dup = await client.post("/api/v1/contacts/",
                            json={"first_name": "Mira", "last_name": "B", "email": "shared@fam.com"},
                            headers=env["admin_h"])
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_patient_allowed_with_flag(client: AsyncClient, env: dict):
    await client.post("/api/v1/contacts/",
                      json={"first_name": "Dad", "last_name": "Family", "phone": "+919222222222"},
                      headers=env["admin_h"])
    # family members legitimately share a phone -> override
    child = await client.post("/api/v1/contacts/",
                              json={"first_name": "Kid", "last_name": "Family", "phone": "+919222222222",
                                    "allow_duplicate": True}, headers=env["admin_h"])
    assert child.status_code == 201, child.text


@pytest.mark.asyncio
async def test_unique_patient_still_creates(client: AsyncClient, env: dict):
    res = await client.post("/api/v1/contacts/",
                            json={"first_name": "Uni", "last_name": "Que", "phone": "+919333333333"},
                            headers=env["admin_h"])
    assert res.status_code == 201

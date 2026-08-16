"""Regression tests for per-tenant invoice settings + customized invoicing:
numbering sequence, currency/branding from settings, patient-centric invoice
creation (auto company), branded PDF, RBAC, and tenant isolation.
"""
import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.contact import Contact
from app.models.customer_invoice import CustomerInvoice


async def _seed(db: AsyncSession, name: str, slug: str):
    org = await OrganizationRepository(db).create({"name": name, "slug": slug})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    emp = await UserRepository(db).create_user(org.id, {
        "email": f"emp@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Eve", "last_name": "Emp", "role": "Employee", "is_active": True})
    await db.commit()
    contact = Contact(organization_id=org.id, first_name="Priya", last_name="Sharma",
                      phone="+919812345678", created_by=admin.id)
    db.add(contact)
    await db.commit()
    return org, admin, emp, contact


@pytest.fixture
async def env(db: AsyncSession):
    org, admin, emp, contact = await _seed(db, "Clinic A", "inv-a")
    return {"org": org, "admin": admin, "emp": emp, "contact": contact,
            "admin_h": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "emp_h": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_settings_defaults_created_on_first_read(client: AsyncClient, env):
    r = await client.get("/api/v1/customers/invoice-settings", headers=env["admin_h"])
    assert r.status_code == 200
    d = r.json()
    assert d["currency"] == "INR" and d["invoice_prefix"] == "INV-" and d["next_invoice_number"] == 1


@pytest.mark.asyncio
async def test_update_settings(client: AsyncClient, env):
    r = await client.put("/api/v1/customers/invoice-settings", headers=env["admin_h"], json={
        "legal_name": "SmileCare Dental", "invoice_prefix": "SC-", "next_invoice_number": 101,
        "default_tax_percent": 18, "currency": "INR", "gst_number": "27ABCDE1234F1Z5"})
    assert r.status_code == 200
    assert r.json()["invoice_prefix"] == "SC-" and r.json()["legal_name"] == "SmileCare Dental"


@pytest.mark.asyncio
async def test_employee_cannot_edit_settings(client: AsyncClient, env):
    r = await client.put("/api/v1/customers/invoice-settings", headers=env["emp_h"], json={"invoice_prefix": "X-"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patient_centric_numbering_and_currency(client: AsyncClient, env, db):
    await client.put("/api/v1/customers/invoice-settings", headers=env["admin_h"], json={
        "invoice_prefix": "SC-", "next_invoice_number": 101, "number_padding": 4, "currency": "INR"})
    # create with contact only (no company) -> company auto-resolved, number from settings
    r1 = await client.post("/api/v1/customers/invoices", headers=env["admin_h"], json={
        "contact_id": str(env["contact"].id), "items": [{"description": "RCT", "quantity": 1, "unit_price": 12000}], "tax_amount": 2160})
    assert r1.status_code == 201, r1.text
    assert r1.json()["invoice_number"] == "SC-0101"
    assert r1.json()["currency"] == "INR"
    assert r1.json()["company_id"]  # auto-created billing company
    assert Decimal(str(r1.json()["total_amount"])) == Decimal("14160")
    # second invoice increments
    r2 = await client.post("/api/v1/customers/invoices", headers=env["admin_h"], json={
        "contact_id": str(env["contact"].id), "items": [{"description": "Cleaning", "quantity": 1, "unit_price": 2500}]})
    assert r2.json()["invoice_number"] == "SC-0102"


@pytest.mark.asyncio
async def test_explicit_currency_overrides_settings(client: AsyncClient, env):
    r = await client.post("/api/v1/customers/invoices", headers=env["admin_h"], json={
        "contact_id": str(env["contact"].id), "currency": "USD", "items": [{"description": "x", "quantity": 1, "unit_price": 10}]})
    assert r.status_code == 201 and r.json()["currency"] == "USD"


@pytest.mark.asyncio
async def test_invoice_missing_patient_and_company_rejected(client: AsyncClient, env):
    r = await client.post("/api/v1/customers/invoices", headers=env["admin_h"], json={
        "items": [{"description": "x", "quantity": 1, "unit_price": 10}]})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_pdf_renders(client: AsyncClient, env):
    inv = (await client.post("/api/v1/customers/invoices", headers=env["admin_h"], json={
        "contact_id": str(env["contact"].id), "items": [{"description": "RCT", "quantity": 1, "unit_price": 12000}]})).json()
    r = await client.get(f"/api/v1/customers/invoices/{inv['id']}/pdf", headers=env["admin_h"])
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_settings_tenant_isolated(client: AsyncClient, env, db):
    await client.put("/api/v1/customers/invoice-settings", headers=env["admin_h"], json={"invoice_prefix": "SC-"})
    _, admin_b, _, _ = await _seed(db, "Clinic B", "inv-b")
    other_h = {"Authorization": f"Bearer {create_access_token(admin_b.id)}"}
    r = await client.get("/api/v1/customers/invoice-settings", headers=other_h)
    assert r.status_code == 200 and r.json()["invoice_prefix"] == "INV-"  # not SC-

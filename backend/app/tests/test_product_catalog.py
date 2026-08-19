"""Regression tests for the generic Product Catalog."""
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository


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
    return org, admin, emp


@pytest.fixture
async def env(db: AsyncSession):
    org, admin, emp = await _seed(db, "Workspace A", "pc-a")
    return {"admin_h": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "emp_h": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_create_and_list_products(client: AsyncClient, env):
    r = await client.post("/api/v1/product-catalog/", headers=env["admin_h"], json={
        "name": "Standard Consultation", "category": "Consulting", "code": "CONS", "price": 5000, "tax_percent": 18,
        "duration_minutes": 30})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Standard Consultation" and Decimal(str(r.json()["price"])) == Decimal("5000")
    lst = await client.get("/api/v1/product-catalog/", headers=env["admin_h"])
    assert lst.status_code == 200 and len(lst.json()) == 1


@pytest.mark.asyncio
async def test_employee_can_read_not_write_products(client: AsyncClient, env):
    # employee can read the price list
    assert (await client.get("/api/v1/product-catalog/", headers=env["emp_h"])).status_code == 200
    # but cannot create/edit
    r = await client.post("/api/v1/product-catalog/", headers=env["emp_h"], json={"name": "X", "price": 10})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_and_delete_products(client: AsyncClient, env):
    item = (await client.post("/api/v1/product-catalog/", headers=env["admin_h"],
                              json={"name": "Audit Service", "price": 20000})).json()
    up = await client.patch(f"/api/v1/product-catalog/{item['id']}", headers=env["admin_h"], json={"price": 25000})
    assert up.status_code == 200 and Decimal(str(up.json()["price"])) == Decimal("25000")
    dele = await client.delete(f"/api/v1/product-catalog/{item['id']}", headers=env["admin_h"])
    assert dele.status_code == 204
    assert (await client.get("/api/v1/product-catalog/", headers=env["admin_h"])).json() == []


@pytest.mark.asyncio
async def test_categories_and_filter_products(client: AsyncClient, env):
    for n, cat in [("Item A", "Hardware"), ("Item B", "Software"), ("Item C", "Cloud")]:
        await client.post("/api/v1/product-catalog/", headers=env["admin_h"], json={"name": n, "category": cat, "price": 100})
    cats = await client.get("/api/v1/product-catalog/categories", headers=env["admin_h"])
    assert cats.status_code == 200 and set(cats.json()) == {"Hardware", "Software", "Cloud"}
    filt = await client.get("/api/v1/product-catalog/", headers=env["admin_h"], params={"category": "Software"})
    assert len(filt.json()) == 1 and filt.json()[0]["name"] == "Item B"


@pytest.mark.asyncio
async def test_negative_price_rejected_products(client: AsyncClient, env):
    r = await client.post("/api/v1/product-catalog/", headers=env["admin_h"], json={"name": "Bad", "price": -5})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tenant_isolation_products(client: AsyncClient, env, db):
    mine = (await client.post("/api/v1/product-catalog/", headers=env["admin_h"],
                              json={"name": "Mine", "price": 1})).json()
    _, admin_b, _ = await _seed(db, "Workspace B", "pc-b")
    other_h = {"Authorization": f"Bearer {create_access_token(admin_b.id)}"}
    assert (await client.get("/api/v1/product-catalog/", headers=other_h)).json() == []
    assert (await client.get(f"/api/v1/product-catalog/{mine['id']}", headers=other_h)).status_code == 404

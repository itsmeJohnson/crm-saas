"""Regression tests for the Treatment & Price master."""
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
    org, admin, emp = await _seed(db, "Clinic A", "tc-a")
    return {"admin_h": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "emp_h": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_create_and_list(client: AsyncClient, env):
    r = await client.post("/api/v1/treatment-catalog/", headers=env["admin_h"], json={
        "name": "Root Canal Therapy", "category": "Endodontics", "code": "RCT", "price": 12000, "tax_percent": 18,
        "duration_minutes": 60})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Root Canal Therapy" and Decimal(str(r.json()["price"])) == Decimal("12000")
    lst = await client.get("/api/v1/treatment-catalog/", headers=env["admin_h"])
    assert lst.status_code == 200 and len(lst.json()) == 1


@pytest.mark.asyncio
async def test_employee_can_read_not_write(client: AsyncClient, env):
    # employee (clinical staff) can read the price list
    assert (await client.get("/api/v1/treatment-catalog/", headers=env["emp_h"])).status_code == 200
    # but cannot create/edit
    r = await client.post("/api/v1/treatment-catalog/", headers=env["emp_h"], json={"name": "X", "price": 10})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_and_delete(client: AsyncClient, env):
    item = (await client.post("/api/v1/treatment-catalog/", headers=env["admin_h"],
                              json={"name": "Cleaning", "price": 2000})).json()
    up = await client.patch(f"/api/v1/treatment-catalog/{item['id']}", headers=env["admin_h"], json={"price": 2500})
    assert up.status_code == 200 and Decimal(str(up.json()["price"])) == Decimal("2500")
    dele = await client.delete(f"/api/v1/treatment-catalog/{item['id']}", headers=env["admin_h"])
    assert dele.status_code == 204
    assert (await client.get("/api/v1/treatment-catalog/", headers=env["admin_h"])).json() == []


@pytest.mark.asyncio
async def test_categories_and_filter(client: AsyncClient, env):
    for n, cat in [("RCT", "Endodontics"), ("Braces", "Orthodontics"), ("Implant", "Implantology")]:
        await client.post("/api/v1/treatment-catalog/", headers=env["admin_h"], json={"name": n, "category": cat, "price": 100})
    cats = await client.get("/api/v1/treatment-catalog/categories", headers=env["admin_h"])
    assert cats.status_code == 200 and set(cats.json()) == {"Endodontics", "Orthodontics", "Implantology"}
    filt = await client.get("/api/v1/treatment-catalog/", headers=env["admin_h"], params={"category": "Orthodontics"})
    assert len(filt.json()) == 1 and filt.json()[0]["name"] == "Braces"


@pytest.mark.asyncio
async def test_negative_price_rejected(client: AsyncClient, env):
    r = await client.post("/api/v1/treatment-catalog/", headers=env["admin_h"], json={"name": "Bad", "price": -5})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, env, db):
    mine = (await client.post("/api/v1/treatment-catalog/", headers=env["admin_h"],
                              json={"name": "Mine", "price": 1})).json()
    _, admin_b, _ = await _seed(db, "Clinic B", "tc-b")
    other_h = {"Authorization": f"Bearer {create_access_token(admin_b.id)}"}
    assert (await client.get("/api/v1/treatment-catalog/", headers=other_h)).json() == []
    assert (await client.get(f"/api/v1/treatment-catalog/{mine['id']}", headers=other_h)).status_code == 404

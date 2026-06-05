import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.user import User

@pytest.fixture
async def setup_assignment_routes_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Setup Org
    org = await org_repo.create({"name": "Assignment Org", "slug": "assign-org"})
    await db.commit()

    # 2. Org A Admin
    admin = await user_repo.create_user(org.id, {
        "email": "admin@assignorg.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })

    # 3. Org A Employee (Regular User)
    employee = await user_repo.create_user(org.id, {
        "email": "employee@assignorg.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Employee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })

    # 4. Inactive Employee (Should be skipped by assignment!)
    inactive_emp = await user_repo.create_user(org.id, {
        "email": "inactive@assignorg.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Inactive",
        "last_name": "B",
        "role": "Employee",
        "is_active": False
    })
    await db.commit()

    # Auth headers
    token_admin = create_access_token(admin.id)
    token_employee = create_access_token(employee.id)

    return {
        "org": org,
        "admin": admin,
        "employee": employee,
        "inactive_emp": inactive_emp,
        "headers_admin": {"Authorization": f"Bearer {token_admin}"},
        "headers_employee": {"Authorization": f"Bearer {token_employee}"}
    }

@pytest.mark.asyncio
async def test_get_assignment_config_routes(client: AsyncClient, setup_assignment_routes_data: dict):
    data = setup_assignment_routes_data

    # 1. Admin can get config
    resp = await client.get("/api/v1/leads/assignment/config", headers=data["headers_admin"])
    assert resp.status_code == 200
    config = resp.json()
    assert config["is_active"] is True
    assert config["organization_id"] == str(data["org"].id)

    # 2. Employee is blocked (403 Forbidden)
    resp = await client.get("/api/v1/leads/assignment/config", headers=data["headers_employee"])
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_patch_assignment_config_routes(client: AsyncClient, setup_assignment_routes_data: dict):
    data = setup_assignment_routes_data

    # 1. Admin can update config (disable auto assignment)
    payload = {"is_active": False}
    resp = await client.patch("/api/v1/leads/assignment/config", json=payload, headers=data["headers_admin"])
    assert resp.status_code == 200
    config = resp.json()
    assert config["is_active"] is False

    # 2. Employee is blocked from updating
    resp = await client.patch("/api/v1/leads/assignment/config", json=payload, headers=data["headers_employee"])
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_lead_creation_auto_assignment_skips_inactive(client: AsyncClient, setup_assignment_routes_data: dict, db: AsyncSession):
    data = setup_assignment_routes_data

    # The organization setup has:
    # 1 active admin
    # 1 active employee
    # 1 inactive employee
    # Auto-assignment distributes leads to active employees only.
    # Therefore, the lead MUST be assigned to employee (active) and NOT inactive_emp.

    # 1. Ensure config is enabled
    await client.patch("/api/v1/leads/assignment/config", json={"is_active": True}, headers=data["headers_admin"])

    # 2. Post a new lead
    payload = {
        "title": "Lead with Active Employee Auto Assignment",
        "last_name": "TestLead",
        "status": "New"
    }

    resp = await client.post("/api/v1/leads/", json=payload, headers=data["headers_admin"])
    assert resp.status_code == 201
    lead_data = resp.json()
    
    # 3. Assert assignment went to active employee
    assert lead_data["assigned_user_id"] == str(data["employee"].id)
    assert lead_data["assigned_user_id"] != str(data["inactive_emp"].id)

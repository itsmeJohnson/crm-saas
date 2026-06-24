import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import create_access_token, get_password_hash

@pytest.fixture
async def setup_users(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Create Organization A
    org_a = await org_repo.create({"name": "Organization A", "slug": "org-a"})
    # Create Organization B
    org_b = await org_repo.create({"name": "Organization B", "slug": "org-b"})
    await db.commit()

    # Create Users for Org A
    admin_a = await user_repo.create_user(org_a.id, {
        "email": "admin@org-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    manager_a = await user_repo.create_user(org_a.id, {
        "email": "manager@org-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "A",
        "role": "Manager",
        "is_active": True
    })
    employee_a = await user_repo.create_user(org_a.id, {
        "email": "employee@org-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Employee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })

    # Create Users for Org B
    admin_b = await user_repo.create_user(org_b.id, {
        "email": "admin@org-b.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # Generate tokens
    token_admin_a = create_access_token(admin_a.id)
    token_manager_a = create_access_token(manager_a.id)
    token_employee_a = create_access_token(employee_a.id)
    token_admin_b = create_access_token(admin_b.id)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "manager_a": manager_a,
        "employee_a": employee_a,
        "admin_b": admin_b,
        "headers_admin_a": {"Authorization": f"Bearer {token_admin_a}"},
        "headers_manager_a": {"Authorization": f"Bearer {token_manager_a}"},
        "headers_employee_a": {"Authorization": f"Bearer {token_employee_a}"},
        "headers_admin_b": {"Authorization": f"Bearer {token_admin_b}"},
    }

@pytest.mark.asyncio
async def test_create_user_rbac(client: AsyncClient, setup_users: dict):
    data = setup_users
    # OrgAdmin can create Manager
    payload = {
        "email": "new_manager@org-a.com",
        "first_name": "New",
        "last_name": "Manager",
        "role": "Manager",
        "password": "securepassword123",
        "organization_id": str(data["org_a"].id)
    }
    response = await client.post("/api/v1/users/", json=payload, headers=data["headers_admin_a"])
    assert response.status_code == 201
    assert response.json()["email"] == "new_manager@org-a.com"

    # Manager can create Employee
    payload_employee = {
        "email": "new_employee@org-a.com",
        "first_name": "New",
        "last_name": "Employee",
        "role": "Employee",
        "password": "securepassword123",
        "organization_id": str(data["org_a"].id)
    }
    response = await client.post("/api/v1/users/", json=payload_employee, headers=data["headers_manager_a"])
    assert response.status_code == 201
    assert response.json()["email"] == "new_employee@org-a.com"

    # Manager cannot create OrgAdmin
    payload_admin = {
        "email": "new_admin@org-a.com",
        "first_name": "New",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "password": "securepassword123",
        "organization_id": str(data["org_a"].id)
    }
    response = await client.post("/api/v1/users/", json=payload_admin, headers=data["headers_manager_a"])
    assert response.status_code == 403

    # Employee cannot create user
    response = await client.post("/api/v1/users/", json=payload_employee, headers=data["headers_employee_a"])
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_list_users_scoping_and_pagination(client: AsyncClient, setup_users: dict):
    data = setup_users
    # List Org A users as Admin A
    response = await client.get("/api/v1/users/", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 3
    emails = [u["email"] for u in res_data]
    assert "admin@org-a.com" in emails
    assert "manager@org-a.com" in emails
    assert "employee@org-a.com" in emails
    assert "admin@org-b.com" not in emails

    # List with search
    response = await client.get("/api/v1/users/?search=manager", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 1
    assert res_data[0]["email"] == "manager@org-a.com"

    # List with limit
    response = await client.get("/api/v1/users/?limit=1", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 1

    # List with role filter
    response = await client.get("/api/v1/users/?role=Employee", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 1
    assert res_data[0]["email"] == "employee@org-a.com"

    # List with active filter (true)
    response = await client.get("/api/v1/users/?is_active=true", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 3

    # List with active filter (false)
    response = await client.get("/api/v1/users/?is_active=false", headers=data["headers_admin_a"])
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 0

    # Employee cannot list users
    response = await client.get("/api/v1/users/", headers=data["headers_employee_a"])
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient, setup_users: dict):
    data = setup_users
    # Get self details
    response = await client.get(f"/api/v1/users/{data['employee_a'].id}", headers=data["headers_employee_a"])
    assert response.status_code == 200
    assert response.json()["email"] == "employee@org-a.com"

    # Get details of other user in organization as Manager
    response = await client.get(f"/api/v1/users/{data['employee_a'].id}", headers=data["headers_manager_a"])
    assert response.status_code == 200
    assert response.json()["email"] == "employee@org-a.com"

    # Tenant isolation: Get Org B user details as Org A user (should fail)
    response = await client.get(f"/api/v1/users/{data['admin_b'].id}", headers=data["headers_admin_a"])
    assert response.status_code == 404

    # Employee tries to get another user's details (should fail)
    response = await client.get(f"/api/v1/users/{data['admin_a'].id}", headers=data["headers_employee_a"])
    assert response.status_code == 403

    # Manager tries to get Admin's details (should fail)
    response = await client.get(f"/api/v1/users/{data['admin_a'].id}", headers=data["headers_manager_a"])
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, setup_users: dict):
    data = setup_users
    # Employee updates self (fields first_name/last_name)
    update_payload = {"first_name": "UpdatedEmployeeName"}
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}", json=update_payload, headers=data["headers_employee_a"])
    assert response.status_code == 200
    assert response.json()["first_name"] == "UpdatedEmployeeName"

    # Employee tries to update role (should fail)
    update_payload = {"role": "OrgAdmin"}
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}", json=update_payload, headers=data["headers_employee_a"])
    assert response.status_code == 403

    # Manager updates Employee (should succeed)
    update_payload = {"first_name": "ManagerUpdated"}
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}", json=update_payload, headers=data["headers_manager_a"])
    assert response.status_code == 200
    assert response.json()["first_name"] == "ManagerUpdated"

    # Manager tries to demote Admin A (should fail)
    update_payload = {"role": "Employee"}
    response = await client.patch(f"/api/v1/users/{data['admin_a'].id}", json=update_payload, headers=data["headers_manager_a"])
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_toggle_user_status(client: AsyncClient, setup_users: dict):
    data = setup_users
    # OrgAdmin deactivates Employee
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}/status?is_active=false", headers=data["headers_admin_a"])
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # OrgAdmin deactivates self (should fail)
    response = await client.patch(f"/api/v1/users/{data['admin_a'].id}/status?is_active=false", headers=data["headers_admin_a"])
    assert response.status_code == 400

    # Manager deactivates Employee (should succeed under relaxed rules)
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}/status?is_active=false", headers=data["headers_manager_a"])
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Manager tries to deactivate Admin (should fail)
    response = await client.patch(f"/api/v1/users/{data['admin_a'].id}/status?is_active=false", headers=data["headers_manager_a"])
    assert response.status_code == 403

    # Deactivated Employee tries to perform an action (should be blocked with 400 Inactive User)
    response = await client.get("/api/v1/users/", headers=data["headers_employee_a"])
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, setup_users: dict):
    data = setup_users
    # OrgAdmin deletes Employee A
    response = await client.delete(f"/api/v1/users/{data['employee_a'].id}", headers=data["headers_admin_a"])
    assert response.status_code == 200
    
    # Verify deletion in list
    response_list = await client.get("/api/v1/users/", headers=data["headers_admin_a"])
    assert len(response_list.json()) == 2

    # OrgAdmin deletes self (should fail)
    response = await client.delete(f"/api/v1/users/{data['admin_a'].id}", headers=data["headers_admin_a"])
    assert response.status_code == 400

    # Manager tries to delete Admin A (should fail)
    response = await client.delete(f"/api/v1/users/{data['admin_a'].id}", headers=data["headers_manager_a"])
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_manager_admin_change_reporting_manager(client: AsyncClient, setup_users: dict):
    data = setup_users
    # Manager changes employee_a reporting manager to manager_a
    payload = {"reporting_to_id": str(data["manager_a"].id)}
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}", json=payload, headers=data["headers_manager_a"])
    assert response.status_code == 200
    assert response.json()["reporting_to_id"] == str(data["manager_a"].id)

    # OrgAdmin changes employee_a reporting manager to None
    payload = {"reporting_to_id": None}
    response = await client.patch(f"/api/v1/users/{data['employee_a'].id}", json=payload, headers=data["headers_admin_a"])
    assert response.status_code == 200
    assert response.json()["reporting_to_id"] is None

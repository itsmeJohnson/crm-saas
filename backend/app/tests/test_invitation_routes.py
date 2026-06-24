import pytest
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.invitation_repository import InvitationRepository
from app.core.security import create_access_token, get_password_hash

@pytest.fixture
async def setup_invites(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    invite_repo = InvitationRepository(db)

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
async def test_create_and_list_invitations(client: AsyncClient, setup_invites: dict):
    data = setup_invites

    # OrgAdmin A invites a Manager
    payload = {
        "email": "invited_manager@org-a.com",
        "role": "Manager"
    }
    response = await client.post("/api/v1/users/invitations", json=payload, headers=data["headers_admin_a"])
    assert response.status_code == 201
    inv_data = response.json()
    assert inv_data["email"] == "invited_manager@org-a.com"
    assert inv_data["role"] == "Manager"
    assert "token" in inv_data

    # Manager A invites an Employee
    payload_employee = {
        "email": "invited_employee@org-a.com",
        "role": "Employee"
    }
    response = await client.post("/api/v1/users/invitations", json=payload_employee, headers=data["headers_manager_a"])
    assert response.status_code == 201

    # Employee A tries to invite (should fail)
    response = await client.post("/api/v1/users/invitations", json=payload_employee, headers=data["headers_employee_a"])
    assert response.status_code == 403

    # Manager A tries to invite an OrgAdmin (should fail)
    payload_admin = {
        "email": "invited_admin@org-a.com",
        "role": "OrgAdmin"
    }
    response = await client.post("/api/v1/users/invitations", json=payload_admin, headers=data["headers_manager_a"])
    assert response.status_code == 403

    # OrgAdmin A lists pending invitations
    response = await client.get("/api/v1/users/invitations", headers=data["headers_admin_a"])
    assert response.status_code == 200
    pending_list = response.json()
    assert len(pending_list) == 2
    emails = [i["email"] for i in pending_list]
    assert "invited_manager@org-a.com" in emails
    assert "invited_employee@org-a.com" in emails

    # OrgAdmin B lists pending invitations (should see 0, tenant isolation)
    response = await client.get("/api/v1/users/invitations", headers=data["headers_admin_b"])
    assert response.status_code == 200
    assert len(response.json()) == 0

@pytest.mark.asyncio
async def test_accept_invitation_flow(client: AsyncClient, setup_invites: dict):
    data = setup_invites

    # Create invitation
    payload = {
        "email": "invited_new_user@org-a.com",
        "role": "Employee"
    }
    response = await client.post("/api/v1/users/invitations", json=payload, headers=data["headers_admin_a"])
    assert response.status_code == 201
    invite_token = response.json()["token"]

    # Accept invitation (Public endpoint, no auth header needed)
    accept_payload = {
        "token": invite_token,
        "password": "newuserpassword123",
        "first_name": "Invited",
        "last_name": "Employee"
    }
    response = await client.post("/api/v1/users/invitations/accept", json=accept_payload)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "invited_new_user@org-a.com"
    assert user_data["role"] == "Employee"
    assert user_data["is_active"] is True
    assert user_data["is_invited"] is True
    assert user_data["is_verified"] is True

    # Try to reuse the token (should fail)
    response = await client.post("/api/v1/users/invitations/accept", json=accept_payload)
    assert response.status_code == 400
    assert "no longer active" in response.json()["detail"]

@pytest.mark.asyncio
async def test_accept_expired_invitation(client: AsyncClient, db: AsyncSession, setup_invites: dict):
    data = setup_invites
    invite_repo = InvitationRepository(db)

    # Insert an expired invitation manually to test expiration
    expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    invite_data = {
        "email": "expired@org-a.com",
        "role": "Employee",
        "token": "expired_token_12345",
        "expires_at": expires_at,
        "created_by": data["admin_a"].id
    }
    await invite_repo.create_invitation(data["org_a"].id, invite_data)
    await db.commit()

    # Accept expired invitation
    accept_payload = {
        "token": "expired_token_12345",
        "password": "newuserpassword123",
        "first_name": "Expired",
        "last_name": "User"
    }
    response = await client.post("/api/v1/users/invitations/accept", json=accept_payload)
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]

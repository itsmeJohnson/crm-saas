import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import create_access_token, get_password_hash

@pytest.fixture
async def setup_crm_routes_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Setup Org A and Org B
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # Active User in Org A
    user_a = await user_repo.create_user(org_a.id, {
        "email": "admin@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    # Active User in Org B
    user_b = await user_repo.create_user(org_b.id, {
        "email": "admin@tenant-b.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    token_a = create_access_token(user_a.id)
    token_b = create_access_token(user_b.id)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"}
    }

@pytest.mark.asyncio
async def test_company_endpoints(client: AsyncClient, setup_crm_routes_data: dict):
    data = setup_crm_routes_data

    # POST create
    payload = {"name": "Test Company", "domain": "test.com", "industry": "Tech"}
    response = await client.post("/api/v1/companies/", json=payload, headers=data["headers_a"])
    assert response.status_code == 201
    comp_json = response.json()
    assert comp_json["name"] == "Test Company"
    comp_id = comp_json["id"]

    # GET list
    response = await client.get("/api/v1/companies/", headers=data["headers_a"])
    assert response.status_code == 200
    assert len(response.json()) == 1

    # GET list as tenant B (should be empty)
    response = await client.get("/api/v1/companies/", headers=data["headers_b"])
    assert response.status_code == 200
    assert len(response.json()) == 0

    # GET detail
    response = await client.get(f"/api/v1/companies/{comp_id}", headers=data["headers_a"])
    assert response.status_code == 200

    # GET detail as tenant B (should return 404)
    response = await client.get(f"/api/v1/companies/{comp_id}", headers=data["headers_b"])
    assert response.status_code == 404

    # PATCH update
    response = await client.patch(
        f"/api/v1/companies/{comp_id}",
        json={"name": "Updated Name"},
        headers=data["headers_a"]
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"

    # DELETE
    response = await client.delete(f"/api/v1/companies/{comp_id}", headers=data["headers_a"])
    assert response.status_code == 200

    # Verify deleted
    response = await client.get(f"/api/v1/companies/{comp_id}", headers=data["headers_a"])
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_contact_endpoints(client: AsyncClient, setup_crm_routes_data: dict):
    data = setup_crm_routes_data

    # POST create
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@doe.com",
        "phone": "12345"
    }
    response = await client.post("/api/v1/contacts/", json=payload, headers=data["headers_a"])
    assert response.status_code == 201
    contact_id = response.json()["id"]

    # GET list
    response = await client.get("/api/v1/contacts/?search=John", headers=data["headers_a"])
    assert response.status_code == 200
    assert len(response.json()) == 1

    # PATCH
    response = await client.patch(
        f"/api/v1/contacts/{contact_id}",
        json={"first_name": "Johnny"},
        headers=data["headers_a"]
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Johnny"

    # DELETE
    response = await client.delete(f"/api/v1/contacts/{contact_id}", headers=data["headers_a"])
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_lead_endpoints(client: AsyncClient, setup_crm_routes_data: dict):
    data = setup_crm_routes_data

    # POST create
    payload = {
        "title": "Lead Opp",
        "last_name": "Smith",
        "status": "New",
        "value": 5000.0
    }
    response = await client.post("/api/v1/leads/", json=payload, headers=data["headers_a"])
    assert response.status_code == 201
    lead_id = response.json()["id"]

    # GET list
    response = await client.get("/api/v1/leads/", headers=data["headers_a"])
    assert response.status_code == 200
    assert len(response.json()) == 1

    # DELETE
    response = await client.delete(f"/api/v1/leads/{lead_id}", headers=data["headers_a"])
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_activity_endpoints(client: AsyncClient, setup_crm_routes_data: dict):
    data = setup_crm_routes_data

    # POST create
    payload = {
        "activity_type": "Meeting",
        "subject": "Strategy Sync",
        "status": "Planned"
    }
    response = await client.post("/api/v1/activities/", json=payload, headers=data["headers_a"])
    assert response.status_code == 201
    activity_id = response.json()["id"]

    # GET list
    response = await client.get("/api/v1/activities/?status=Planned", headers=data["headers_a"])
    assert response.status_code == 200
    assert len(response.json()) == 1

    # DELETE
    response = await client.delete(f"/api/v1/activities/{activity_id}", headers=data["headers_a"])
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_note_endpoints(client: AsyncClient, setup_crm_routes_data: dict):
    data = setup_crm_routes_data

    # 1. Create a lead to link the note to
    lead_resp = await client.post(
        "/api/v1/leads/",
        json={"title": "Note Parent", "last_name": "Bond", "status": "New"},
        headers=data["headers_a"]
    )
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    # 2. POST create note linked to the lead
    payload = {
        "content": "This is a detailed call log note.",
        "lead_id": lead_id
    }
    response = await client.post("/api/v1/notes/", json=payload, headers=data["headers_a"])
    assert response.status_code == 201
    note_id = response.json()["id"]

    # 3. GET list notes
    response = await client.get(f"/api/v1/notes/?lead_id={lead_id}", headers=data["headers_a"])
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 4. PATCH update note content
    response = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "Updated notes."},
        headers=data["headers_a"]
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Updated notes."

    # 5. DELETE note
    response = await client.delete(f"/api/v1/notes/{note_id}", headers=data["headers_a"])
    assert response.status_code == 200

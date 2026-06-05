import pytest
import io
import csv
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.core.redis import redis_client

@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}
    async def mock_get(key: str) -> str | None:
        return storage.get(key)
    async def mock_set(key: str, value: str, ex: int = 300) -> bool:
        storage[key] = value
        return True
    async def mock_delete(key: str) -> bool:
        storage.pop(key, None)
        return True
    
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)
    return storage

@pytest.fixture
async def setup_import_routes_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Setup Org A and Org B
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Org A Admin
    admin_a = await user_repo.create_user(org_a.id, {
        "email": "admin@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })

    # 3. Org A Manager
    manager_a = await user_repo.create_user(org_a.id, {
        "email": "manager@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "A",
        "role": "Manager",
        "is_active": True
    })

    # 4. Org A Employee (Regular User)
    employee_a = await user_repo.create_user(org_a.id, {
        "email": "employee@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Employee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })

    # 5. Org B Admin (Other tenant admin)
    admin_b = await user_repo.create_user(org_b.id, {
        "email": "admin@tenant-b.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # Auth headers
    token_admin_a = create_access_token(admin_a.id)
    token_manager_a = create_access_token(manager_a.id)
    token_employee_a = create_access_token(employee_a.id)
    token_admin_b = create_access_token(admin_b.id)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "headers_admin_a": {"Authorization": f"Bearer {token_admin_a}"},
        "headers_manager_a": {"Authorization": f"Bearer {token_manager_a}"},
        "headers_employee_a": {"Authorization": f"Bearer {token_employee_a}"},
        "headers_admin_b": {"Authorization": f"Bearer {token_admin_b}"}
    }

@pytest.mark.asyncio
async def test_get_import_template_route(client: AsyncClient, setup_import_routes_data: dict):
    data = setup_import_routes_data
    
    # 1. Admin A can download template
    resp = await client.get("/api/v1/leads/import/template?format=csv", headers=data["headers_admin_a"])
    assert resp.status_code == 200
    assert "First Name,Last Name,Email,Phone,Company,Title,Deal Value,Source" in resp.text

    # 2. Manager A can download template
    resp = await client.get("/api/v1/leads/import/template?format=csv", headers=data["headers_manager_a"])
    assert resp.status_code == 200

    # 3. Employee A is blocked (403 Forbidden)
    resp = await client.get("/api/v1/leads/import/template?format=csv", headers=data["headers_employee_a"])
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_import_upload_and_preview_flow(client: AsyncClient, setup_import_routes_data: dict):
    data = setup_import_routes_data

    # Valid CSV content
    csv_content = b"First Name,Last Name,Email,Phone,Company,Title,Deal Value,Source\nJohn,Doe,johndoe@test.com,555-0011,Acme,CEO,50000,Web"

    # 1. Admin A uploads file
    files = {"file": ("leads.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/leads/import/upload", files=files, headers=data["headers_admin_a"])
    assert resp.status_code == 200
    preview = resp.json()
    assert preview["file_token"] is not None
    assert "First Name" in preview["headers"]
    assert preview["suggested_mapping"]["first_name"]["column"] == "First Name"

    # 2. Employee A upload is blocked
    files = {"file": ("leads.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/leads/import/upload", files=files, headers=data["headers_employee_a"])
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_import_file_size_limits(client: AsyncClient, setup_import_routes_data: dict):
    data = setup_import_routes_data

    # File exceeding 5MB size limit
    large_content = b"a" * (5 * 1024 * 1024 + 10)
    files = {"file": ("leads.csv", large_content, "text/csv")}
    resp = await client.post("/api/v1/leads/import/upload", files=files, headers=data["headers_admin_a"])
    assert resp.status_code == 400
    assert "exceeds 5MB limit" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_invalid_google_sheets_url(client: AsyncClient, setup_import_routes_data: dict):
    data = setup_import_routes_data

    payload = {"url": "https://invalid-url.com/sheet"}
    resp = await client.post("/api/v1/leads/import/google-sheets", json=payload, headers=data["headers_admin_a"])
    assert resp.status_code == 400
    assert "Invalid Google Sheets URL" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_process_import_batch_with_duplicates_and_isolation(client: AsyncClient, setup_import_routes_data: dict, db: AsyncSession):
    data = setup_import_routes_data

    # Create pre-existing duplicate lead inside Org B (other tenant)
    # The duplicate check should be isolated, so Org A can still import the lead.
    other_lead = Lead(
        organization_id=data["org_b"].id,
        first_name="Double",
        last_name="Lead",
        email="test_dup@tenant.com",
        title="Manager",
        created_by=data["admin_b"].id
    )
    db.add(other_lead)
    await db.commit()

    # Pre-existing duplicate inside Org A
    existing_lead_a = Lead(
        organization_id=data["org_a"].id,
        first_name="Double",
        last_name="Lead",
        email="existing_dup@tenant.com",
        title="Developer",
        created_by=data["admin_a"].id
    )
    db.add(existing_lead_a)
    await db.commit()

    # Prepare batch containing:
    # 1. Valid row: test_dup@tenant.com (Duplicate inside Org B, but NOT Org A!)
    # 2. Invalid row: existing_dup@tenant.com (Duplicate inside Org A!)
    # 3. Duplicate row within file batch: duplicate_in_batch@test.com (Double rows)
    csv_rows = [
        ["First Name", "Last Name", "Email Address", "Phone Number", "Company Name", "Job Title", "Deal Amount", "Source"],
        ["Jane", "Doe", "test_dup@tenant.com", "555-1234", "CorpA", "Director", "100000", "Referral"],
        ["Failed", "Lead", "existing_dup@tenant.com", "555-4321", "CorpB", "Manager", "20000", "Direct"],
        ["Row1", "InBatch", "duplicate_in_batch@test.com", "555-9999", "CorpC", "Sales", "30000", "Web"],
        ["Row2", "InBatch", "duplicate_in_batch@test.com", "555-9999", "CorpC", "Sales", "30000", "Web"]
    ]

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(csv_rows)
    csv_text = out.getvalue()

    file_token = str(uuid.uuid4())
    await redis_client.set(f"import_file:{file_token}", csv_text, ex=300)

    column_mapping = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "company_name": "Company Name",
        "title": "Job Title",
        "value": "Deal Amount",
        "source": "Source"
    }

    # 1. Perform import processing
    payload = {
        "file_token": file_token,
        "source_type": "file",
        "column_mapping": column_mapping,
        "auto_assign": False
    }

    resp = await client.post("/api/v1/leads/import/process", json=payload, headers=data["headers_admin_a"])
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "COMPLETED"
    assert result["total_rows"] == 4
    assert result["successful_rows"] == 2
    assert result["failed_rows"] == 2

    # Assert tenant isolation (other tenant duplicate skipped, only domestic duplicate failed)
    assert len(result["error_summary"]) == 2
    # Fail 1: existing duplicate inside Org A
    assert result["error_summary"][0]["row"] == 3
    assert "Lead with email already exists in your organization" in result["error_summary"][0]["reason"]
    # Fail 2: duplicate in batch (Row 5)
    assert result["error_summary"][1]["row"] == 5
    assert "Duplicate email address found within this import batch" in result["error_summary"][1]["reason"]

    # 2. Verify history retrieval is tenant isolated
    # History A lists Org A imports
    resp_history = await client.get("/api/v1/leads/import/history", headers=data["headers_admin_a"])
    assert resp_history.status_code == 200
    assert len(resp_history.json()) == 1
    assert resp_history.json()[0]["id"] == result["id"]

    # History B is empty
    resp_history_b = await client.get("/api/v1/leads/import/history", headers=data["headers_admin_b"])
    assert resp_history_b.status_code == 200
    assert len(resp_history_b.json()) == 0

    # 3. Verify failed rows download is isolated
    import_id = result["id"]
    # Admin A can download
    resp_csv = await client.get(f"/api/v1/leads/import/{import_id}/failed-rows", headers=data["headers_admin_a"])
    assert resp_csv.status_code == 200
    assert "Import Error Reason" in resp_csv.text

    # Admin B is blocked from downloading Org A's failed rows
    resp_csv_b = await client.get(f"/api/v1/leads/import/{import_id}/failed-rows", headers=data["headers_admin_b"])
    assert resp_csv_b.status_code == 404

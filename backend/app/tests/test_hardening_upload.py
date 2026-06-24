import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.models.user import User
from app.core.security import create_access_token, get_password_hash
from app.core.storage import validate_and_sanitize_file

def test_file_validation_logic():
    # 1. Valid png
    valid_png_content = b"\x89PNG\r\n\x1a\nSomePNGDataHere"
    filename, ext = validate_and_sanitize_file(valid_png_content, "test.png", {"png", "jpg"})
    assert ext == "png"
    assert filename.endswith(".png")
    assert len(filename) > 10

    # 2. Max size validation (limit 10 bytes)
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_file(valid_png_content, "test.png", {"png"}, max_size=5)
    assert "exceeds the limit" in str(exc.value)

    # 3. Invalid extension
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_file(valid_png_content, "test.exe", {"png"})
    assert "not allowed" in str(exc.value)

    # 4. Invalid magic bytes signature (fake png)
    fake_png_content = b"NotAPNGFile"
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_file(fake_png_content, "test.png", {"png"})
    assert "Invalid file signature" in str(exc.value)

    # 5. WEBP validation
    valid_webp = b"RIFFxxxxWEBPxxxx"
    filename, ext = validate_and_sanitize_file(valid_webp, "test.webp", {"webp"})
    assert ext == "webp"
    
    # 6. SVG validation
    valid_svg = b"<svg width='100' height='100'></svg>"
    filename, ext = validate_and_sanitize_file(valid_svg, "test.svg", {"svg"})
    assert ext == "svg"

    # 7. CSV validation
    valid_csv = b"col1,col2,col3\nval1,val2,val3"
    filename, ext = validate_and_sanitize_file(valid_csv, "test.csv", {"csv"})
    assert ext == "csv"


@pytest.fixture
async def setup_super_admin(db: AsyncSession):
    # Create a SuperAdmin organization
    org = Organization(name="SuperAdmin Org", slug="super-admin-org")
    db.add(org)
    await db.flush()

    # Create a SuperAdmin user
    pwd_hash = get_password_hash("password123")
    super_admin = User(
        organization_id=org.id,
        email="superadmin@test.com",
        hashed_password=pwd_hash,
        first_name="Super",
        last_name="Admin",
        role="SuperAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(super_admin)
    await db.flush()
    await db.commit()

    token = create_access_token(super_admin.id)
    return {
        "org": org,
        "super_admin": super_admin,
        "headers": {"Authorization": f"Bearer {token}"}
    }


@pytest.mark.asyncio
async def test_logo_upload_route_validation(client: AsyncClient, setup_super_admin: dict):
    headers = setup_super_admin["headers"]

    # 1. Valid upload
    valid_png = b"\x89PNG\r\n\x1a\nValidPNGContent"
    files = {"file": ("logo.png", valid_png, "image/png")}
    response = await client.post("/api/v1/super-admin/invoice-config/upload-logo", files=files, headers=headers)
    assert response.status_code == 200
    assert response.json()["company_logo_url"] is not None

    # 2. Fake signature upload (sends html disguised as png)
    fake_png = b"<html>NotAPNG</html>"
    files = {"file": ("logo.png", fake_png, "image/png")}
    response = await client.post("/api/v1/super-admin/invoice-config/upload-logo", files=files, headers=headers)
    assert response.status_code == 400
    assert "Invalid file signature" in response.json()["detail"]

    # 3. Oversized logo upload (limit is 2MB)
    large_data = b"a" * (2 * 1024 * 1024 + 10)
    files = {"file": ("logo.png", large_data, "image/png")}
    response = await client.post("/api/v1/super-admin/invoice-config/upload-logo", files=files, headers=headers)
    assert response.status_code == 400
    assert "exceeds the limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_lead_import_upload_validation(client: AsyncClient):
    # Register/login normal user (leads needs at least Team Leader or above role)
    # We can create a user, assign them OrgAdmin role.
    reg_payload = {
        "company_name": "Leads Corp",
        "slug": "leadscorp",
        "admin_email": "admin@leadscorp.com",
        "admin_password": "supersecurepassword123",
        "first_name": "Leads",
        "last_name": "Tester"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200
    
    # Login to get access token
    login_payload = {
        "email": "admin@leadscorp.com",
        "password": "supersecurepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    tokens = response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 1. Valid CSV import file
    valid_csv = b"first_name,last_name,email,phone\nJohn,Doe,john@doe.com,9999999999"
    files = {"file": ("leads.csv", valid_csv, "text/csv")}
    response = await client.post("/api/v1/leads/import/upload", files=files, headers=headers)
    assert response.status_code == 200
    assert "headers" in response.json()

    # 2. Invalid signature CSV (binary execution content under .csv extension)
    fake_csv = b"\xff\xd8\xffNotACSV"
    files = {"file": ("leads.csv", fake_csv, "text/csv")}
    response = await client.post("/api/v1/leads/import/upload", files=files, headers=headers)
    assert response.status_code == 400
    assert "Invalid file content" in response.json()["detail"]

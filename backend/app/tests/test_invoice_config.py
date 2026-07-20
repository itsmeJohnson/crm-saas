import pytest
import uuid
import io
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.invoice_config import InvoiceConfig
from app.models.plan import Plan
from app.core.security import create_access_token, get_password_hash

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
    
    # Initialize default InvoiceConfig
    config = InvoiceConfig(
        id="default",
        company_name="Johnson Test Softwares",
        invoice_prefix="JNT",
        starting_invoice_number=100,
        currency="INR",
        currency_symbol="₹"
    )
    db.add(config)
    await db.flush()
    await db.commit()

    token = create_access_token(super_admin.id)
    return {
        "org": org,
        "super_admin": super_admin,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_get_invoice_config(client: AsyncClient, setup_super_admin: dict):
    headers = setup_super_admin["headers"]
    response = await client.get("/api/v1/super-admin/invoice-config", headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["company_name"] == "Johnson Test Softwares"
    assert res_data["invoice_prefix"] == "JNT"
    assert res_data["starting_invoice_number"] == 100

@pytest.mark.asyncio
async def test_update_invoice_config(client: AsyncClient, setup_super_admin: dict, db: AsyncSession):
    headers = setup_super_admin["headers"]
    org_id = setup_super_admin["org"].id

    payload = {
        "company_name": "Updated Johnson Softwares",
        "tagline": "Beyond Code",
        "invoice_prefix": "JNJ",
        "starting_invoice_number": 200,
        "currency": "USD",
        "currency_symbol": "$",
        "bank_name": "Test Bank",
        "account_number": "987654321",
        "ifsc": "TEST0001"
    }
    response = await client.put("/api/v1/super-admin/invoice-config", json=payload, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["company_name"] == "Updated Johnson Softwares"
    assert res_data["tagline"] == "Beyond Code"
    assert res_data["invoice_prefix"] == "JNJ"
    assert res_data["starting_invoice_number"] == 200

    # Verify audit logs created
    query = select(AuditLog).where(
        AuditLog.organization_id == org_id,
        AuditLog.action == "INVOICE_CONFIG_UPDATED"
    )
    res = await db.execute(query)
    logs = res.scalars().all()
    assert len(logs) > 0
    audit_meta = logs[0].action_metadata
    assert audit_meta["new"]["company_name"] == "Updated Johnson Softwares"
    assert audit_meta["old"]["company_name"] == "Johnson Test Softwares"

@pytest.mark.asyncio
async def test_upload_delete_branding_files(client: AsyncClient, setup_super_admin: dict, db: AsyncSession):
    headers = setup_super_admin["headers"]
    org_id = setup_super_admin["org"].id

    # 1. Upload company logo file
    logo_file = ("test_logo.png", b"\x89PNG\r\n\x1a\nfake_png_data", "image/png")
    response_logo = await client.post(
        "/api/v1/super-admin/invoice-config/upload-logo",
        files={"file": logo_file},
        headers=headers
    )
    assert response_logo.status_code == 200
    res_logo = response_logo.json()
    assert "/api/v1/uploads/branding/" in res_logo["company_logo_url"]
    assert res_logo["company_logo_url"].endswith(".png")

    # Verify audit log for logo upload
    res_audit_logo = await db.execute(
        select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "INVOICE_LOGO_UPDATED")
    )
    assert res_audit_logo.scalar() is not None

    # 2. Upload payment QR code file
    qr_file = ("test_qr.jpg", b"\xff\xd8\xfffake_jpg_data", "image/jpeg")
    response_qr = await client.post(
        "/api/v1/super-admin/invoice-config/upload-qr",
        files={"file": qr_file},
        headers=headers
    )
    assert response_qr.status_code == 200
    res_qr = response_qr.json()
    assert "/api/v1/uploads/branding/" in res_qr["qr_code_url"]
    assert res_qr["qr_code_url"].endswith(".jpg") or res_qr["qr_code_url"].endswith(".jpeg")

    # Verify audit log for QR upload
    res_audit_qr = await db.execute(
        select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "INVOICE_QR_UPDATED")
    )
    assert res_audit_qr.scalar() is not None

    # 3. Delete company logo
    response_del_logo = await client.delete("/api/v1/super-admin/invoice-config/logo", headers=headers)
    assert response_del_logo.status_code == 200
    assert response_del_logo.json()["company_logo_url"] is None

    # Verify audit log for logo deletion
    res_audit_del_logo = await db.execute(
        select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "INVOICE_LOGO_DELETED")
    )
    assert res_audit_del_logo.scalar() is not None

    # 4. Delete payment QR code
    response_del_qr = await client.delete("/api/v1/super-admin/invoice-config/qr", headers=headers)
    assert response_del_qr.status_code == 200
    assert response_del_qr.json()["qr_code_url"] is None

    # Verify audit log for QR deletion
    res_audit_del_qr = await db.execute(
        select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "INVOICE_QR_DELETED")
    )
    assert res_audit_del_qr.scalar() is not None

@pytest.mark.asyncio
async def test_plan_commercial_validations(client: AsyncClient, setup_super_admin: dict):
    headers = setup_super_admin["headers"]

    # Test bad values (trial_days too large, negative discount, negative GST)
    bad_payload = {
        "name": "enterprise-invalid",
        "display_name": "Enterprise Invalid Plan",
        "monthly_price": 500,
        "quarterly_price": 1400,
        "annual_price": 5000,
        "currency": "INR",
        "max_users": 10,
        "max_admins": 2,
        "max_managers": 2,
        "max_team_leads": 2,
        "max_employees": 6,
        "storage_limit_gb": 10,
        "recording_retention_days": 30,
        "priority_support": True,
        "api_access": True,
        "display_order": 1,
        "setup_charges": 0,
        "minimum_users": 1,
        "maximum_users": 50,
        "minimum_contract_months": 1,
        "trial_days": 400,  # Invalid (> 365)
        "extra_user_price": -10,  # Invalid (< 0)
        "discount_percentage": 110,  # Invalid (> 100)
        "gst_percentage": -5,  # Invalid (< 0)
        "popular_plan": False,
        "recommended_plan": False,
        "allow_upgrade": True,
        "allow_downgrade": True,
        "allow_trial": True,
        "auto_renew": True,
        "plan_active": True
    }
    response = await client.post("/api/v1/super-admin/plans", json=bad_payload, headers=headers)
    assert response.status_code == 422  # Validation Error
    errors = response.json()["detail"]
    # Check that error fields are included in detail messages
    err_types = [err["loc"][-1] for err in errors]
    assert "trial_days" in err_types
    assert "extra_user_price" in err_types
    assert "discount_percentage" in err_types
    assert "gst_percentage" in err_types

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository

async def create_tenant(db: AsyncSession, name: str, slug: str, industry: str = "healthcare_dental", business_template: str = "healthcare_dental", enabled_modules: list = None):
    org = await OrganizationRepository(db).create({
        "name": name,
        "slug": slug,
        "industry": industry,
        "business_template": business_template,
        "enabled_modules": enabled_modules
    })
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Ada",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()
    return org, admin

@pytest.mark.asyncio
async def test_dental_tenant_access_and_bootstrap(client: AsyncClient, db: AsyncSession):
    # Setup standard dental tenant
    org, admin = await create_tenant(db, "Dental Practice A", "dental-a")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}

    # 1. Access gated treatments catalog - should succeed (either 200 or another success status)
    r = await client.get("/api/v1/treatment-catalog/", headers=headers)
    assert r.status_code == 200

    # 2. Bootstrap should include crm_config matching dental default modules
    boot = await client.get("/api/v1/metadata/bootstrap", headers=headers)
    assert boot.status_code == 200
    crm_config = boot.json().get("crm_config")
    assert crm_config is not None
    assert crm_config["industry"] == "healthcare_dental"
    assert crm_config["template"] == "healthcare_dental"
    assert "treatments" in crm_config["enabled_modules"]
    assert "patients" in crm_config["enabled_modules"]

@pytest.mark.asyncio
async def test_real_estate_tenant_access_blocked_and_bootstrap(client: AsyncClient, db: AsyncSession):
    # Setup Real Estate tenant
    org, admin = await create_tenant(db, "Real Estate Agency B", "re-b", industry="real_estate", business_template="real_estate")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}

    # 1. Access gated treatments catalog - should fail with 403 Forbidden because 'treatments' is not enabled
    r = await client.get("/api/v1/treatment-catalog/", headers=headers)
    assert r.status_code == 403
    assert "not enabled" in r.json().get("detail", "")

    # 2. Bootstrap should include crm_config matching real_estate default modules
    boot = await client.get("/api/v1/metadata/bootstrap", headers=headers)
    assert boot.status_code == 200
    crm_config = boot.json().get("crm_config")
    assert crm_config is not None
    assert crm_config["industry"] == "real_estate"
    assert crm_config["template"] == "real_estate"
    assert "treatments" not in crm_config["enabled_modules"]
    assert "patients" not in crm_config["enabled_modules"]
    assert "opportunities" in crm_config["enabled_modules"]
    assert "pipelines" in crm_config["enabled_modules"]

@pytest.mark.asyncio
async def test_tenant_override_modules(client: AsyncClient, db: AsyncSession):
    # Setup tenant with custom overrides (only dashboard and leads enabled)
    org, admin = await create_tenant(
        db, "Limited Agent C", "lim-c", 
        industry="generic", business_template="generic",
        enabled_modules=["dashboard", "leads"]
    )
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}

    boot = await client.get("/api/v1/metadata/bootstrap", headers=headers)
    assert boot.status_code == 200
    crm_config = boot.json().get("crm_config")
    assert crm_config is not None
    assert set(crm_config["enabled_modules"]) == {"dashboard", "leads"}

@pytest.mark.asyncio
async def test_tenant_isolation_boundary(client: AsyncClient, db: AsyncSession):
    # Tenant A: Dental (treatments enabled)
    org_a, admin_a = await create_tenant(db, "Tenant A Dental", "tenant-a")
    headers_a = {"Authorization": f"Bearer {create_access_token(admin_a.id)}"}

    # Tenant B: Real Estate (treatments disabled)
    org_b, admin_b = await create_tenant(db, "Tenant B Real Estate", "tenant-b", industry="real_estate", business_template="real_estate")
    headers_b = {"Authorization": f"Bearer {create_access_token(admin_b.id)}"}

    # Tenant B must be blocked from Tenant A's enabled modules
    r_b = await client.get("/api/v1/treatment-catalog/", headers=headers_b)
    assert r_b.status_code == 403

    # Tenant A must still be allowed access
    r_a = await client.get("/api/v1/treatment-catalog/", headers=headers_a)
    assert r_a.status_code == 200

@pytest.mark.asyncio
async def test_insurance_and_loan_recovery_templates(client: AsyncClient, db: AsyncSession):
    # Setup Insurance Tenant
    org_ins, admin_ins = await create_tenant(db, "Insurance Corp", "ins-corp", industry="insurance", business_template="insurance")
    headers_ins = {"Authorization": f"Bearer {create_access_token(admin_ins.id)}"}

    boot_ins = await client.get("/api/v1/metadata/bootstrap", headers=headers_ins)
    crm_config_ins = boot_ins.json().get("crm_config")
    assert "patients" not in crm_config_ins["enabled_modules"]
    assert "treatments" not in crm_config_ins["enabled_modules"]

    # Setup Loan Recovery Tenant
    org_rec, admin_rec = await create_tenant(db, "Recovery Debt", "rec-debt", industry="loan_recovery", business_template="loan_recovery")
    headers_rec = {"Authorization": f"Bearer {create_access_token(admin_rec.id)}"}

    boot_rec = await client.get("/api/v1/metadata/bootstrap", headers=headers_rec)
    crm_config_rec = boot_rec.json().get("crm_config")
    assert "patients" not in crm_config_rec["enabled_modules"]
    assert "treatments" not in crm_config_rec["enabled_modules"]


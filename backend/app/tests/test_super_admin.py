import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.company import Company
from app.models.pipeline import PipelineStage
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
    await db.flush()
    await db.commit()

    token = create_access_token(super_admin.id)
    return {
        "org": org,
        "super_admin": super_admin,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_super_admin_tenant_operations(client: AsyncClient, setup_super_admin: dict, db: AsyncSession):
    data = setup_super_admin

    # 1. Create a new tenant
    tenant_payload = {
        "company_name": "Test Tenant",
        "slug": "test-tenant",
        "admin_email": "admin@test-tenant.com",
        "admin_password": "password123",
        "first_name": "Tenant",
        "last_name": "Owner"
    }
    response = await client.post("/api/v1/super-admin/tenants", json=tenant_payload, headers=data["headers"])
    assert response.status_code == 201
    org_id = uuid.UUID(response.json()["id"])

    # Verify tenant was created in DB
    org_in_db = await db.get(Organization, org_id)
    assert org_in_db is not None
    assert org_in_db.name == "Test Tenant"

    # Verify primary admin was created
    admin_query = select(User).where(User.organization_id == org_id)
    res = await db.execute(admin_query)
    admin_user = res.scalar_one()
    assert admin_user.email == "admin@test-tenant.com"

    # Fetch seeded PipelineStage for the new tenant
    stages_res = await db.execute(select(PipelineStage).where(PipelineStage.organization_id == org_id))
    stage = stages_res.scalars().first()
    assert stage is not None

    # Create some mock data under this organization to verify cascading delete
    comp = Company(organization_id=org_id, name="Test Company", created_by=admin_user.id)
    lead = Lead(
        organization_id=org_id,
        first_name="John",
        last_name="Doe",
        title="Test Lead",
        company_name="Test Company",
        status="New",
        assigned_user_id=admin_user.id,
        created_by=admin_user.id,
        stage_id=stage.id
    )
    db.add_all([comp, lead])
    await db.flush()
    await db.commit()

    # Verify the records exist in the DB
    assert (await db.execute(select(func.count(Company.id)).where(Company.organization_id == org_id))).scalar() == 1
    assert (await db.execute(select(func.count(Lead.id)).where(Lead.organization_id == org_id))).scalar() == 1

    # 2. List tenants
    response_list = await client.get("/api/v1/super-admin/tenants", headers=data["headers"])
    assert response_list.status_code == 200
    tenants = response_list.json()
    slugs = [t["slug"] for t in tenants]
    assert "test-tenant" in slugs

    # 3. Delete tenant (cascading hard delete)
    response_delete = await client.delete(f"/api/v1/super-admin/tenants/{org_id}", headers=data["headers"])
    assert response_delete.status_code == 200
    assert "deleted successfully" in response_delete.json()["detail"]

    # Verify all records associated with the tenant were hard deleted!
    assert (await db.get(Organization, org_id)) is None
    assert (await db.execute(select(func.count(User.id)).where(User.organization_id == org_id))).scalar() == 0
    assert (await db.execute(select(func.count(Company.id)).where(Company.organization_id == org_id))).scalar() == 0
    assert (await db.execute(select(func.count(Lead.id)).where(Lead.organization_id == org_id))).scalar() == 0

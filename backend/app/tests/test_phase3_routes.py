import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.core.security import create_access_token
from app.services.metadata_validation_engine import MetadataValidationEngine
from app.models.custom_field_definition import CustomFieldDefinition

@pytest.fixture
async def setup_api_data(db: AsyncSession):
    # Create two organizations
    org_a = Organization(name="Route Tenant A", slug="route-tenant-a", metadata_version=1)
    org_b = Organization(name="Route Tenant B", slug="route-tenant-b", metadata_version=1)
    db.add_all([org_a, org_b])
    await db.flush()

    # Org A Users
    admin_a = User(
        organization_id=org_a.id,
        email="admin_a@route-tenant-a.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )
    employee_a = User(
        organization_id=org_a.id,
        email="emp_a@route-tenant-a.com",
        hashed_password="hash",
        role="Employee",
        is_active=True
    )

    # Org B Users
    admin_b = User(
        organization_id=org_b.id,
        email="admin_b@route-tenant-b.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )

    db.add_all([admin_a, employee_a, admin_b])
    await db.flush()
    await db.commit()

    token_admin_a = create_access_token(admin_a.id)
    token_employee_a = create_access_token(employee_a.id)
    token_admin_b = create_access_token(admin_b.id)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "employee_a": employee_a,
        "admin_b": admin_b,
        "headers_admin_a": {"Authorization": f"Bearer {token_admin_a}"},
        "headers_employee_a": {"Authorization": f"Bearer {token_employee_a}"},
        "headers_admin_b": {"Authorization": f"Bearer {token_admin_b}"}
    }


@pytest.mark.asyncio
async def test_consolidated_bootstrap_endpoint(client: AsyncClient, setup_api_data: dict, db: AsyncSession):
    data = setup_api_data
    
    # Seed a custom field for Org A so the bootstrap contents are distinct
    cf = CustomFieldDefinition(
        organization_id=data["org_a"].id,
        entity_type="lead",
        key="custom_text",
        label="Custom Text",
        field_type="text",
        created_by=data["admin_a"].id,
        is_active=True
    )
    db.add(cf)
    await db.commit()

    # 1. Fetch bootstrap configuration for Tenant A
    resp = await client.get("/api/v1/metadata/bootstrap", headers=data["headers_admin_a"])
    assert resp.status_code == 200
    res_data = resp.json()
    assert "metadata_version" in res_data
    assert "custom_fields" in res_data
    assert len(res_data["custom_fields"]) == 1
    assert "pipelines" in res_data
    assert isinstance(res_data["pipelines"], list)

    # Verify tenant isolation: B cannot view A
    resp_b = await client.get("/api/v1/metadata/bootstrap", headers=data["headers_admin_b"])
    assert resp_b.status_code == 200
    res_data_b = resp_b.json()
    assert len(res_data_b["custom_fields"]) == 0
    assert res_data_b != res_data


@pytest.mark.asyncio
async def test_custom_fields_crud_permissions_and_isolation(client: AsyncClient, setup_api_data: dict, db: AsyncSession):
    data = setup_api_data
    headers_admin = data["headers_admin_a"]
    headers_employee = data["headers_employee_a"]

    # 1. Employee lacks permission to create
    payload = {
        "key": "linkedin_profile",
        "label": "LinkedIn Profile",
        "field_type": "text",
        "validation_rules": {"min_length": 5}
    }
    resp = await client.post("/api/v1/metadata/custom-fields", json=payload, headers=headers_employee)
    assert resp.status_code == 403

    # 2. Admin can create successfully
    resp = await client.post("/api/v1/metadata/custom-fields", json=payload, headers=headers_admin)
    assert resp.status_code == 201
    cf_data = resp.json()
    assert cf_data["key"] == "linkedin_profile"
    cf_id = cf_data["id"]

    # Verify organization metadata_version has incremented to 2
    await db.execute(select(Organization)) # Clear session query cache
    org_a = await db.get(Organization, data["org_a"].id)
    assert org_a.metadata_version == 2

    # 3. Tenant B Admin gets 404 attempting to update A's custom field definition
    update_payload = {"label": "Updated Profile Name"}
    resp = await client.patch(f"/api/v1/metadata/custom-fields/{cf_id}", json=update_payload, headers=data["headers_admin_b"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pipelines_and_stages_endpoints(client: AsyncClient, setup_api_data: dict, db: AsyncSession):
    data = setup_api_data
    headers_admin = data["headers_admin_a"]

    # 1. Create pipeline
    pipeline_payload = {
        "name": "Enterprise Inbound",
        "description": "High ticket inbound sales pipeline",
        "is_default": False
    }
    resp = await client.post("/api/v1/pipelines/all", json=pipeline_payload, headers=headers_admin)
    assert resp.status_code == 201
    p_data = resp.json()
    assert p_data["name"] == "Enterprise Inbound"
    p_id = p_data["id"]

    # Verify metadata version has incremented
    await db.execute(select(Organization))
    org_a = await db.get(Organization, data["org_a"].id)
    # The default org creation starts at version 1. Custom field create incremented it to 2 (if run together, but tests run independently).
    # Since tests are independent, this is the first change for this test, so it goes from 1 to 2.
    assert org_a.metadata_version == 2

    # 2. Create stage for pipeline
    stage_payload = {
        "name": "Initial Call",
        "pipeline_id": p_id,
        "order_position": 1,
        "color": "#00FF00"
    }
    resp = await client.post("/api/v1/pipelines/stages", json=stage_payload, headers=headers_admin)
    assert resp.status_code == 201
    s_data = resp.json()
    assert s_data["name"] == "Initial Call"
    assert s_data["pipeline_id"] == p_id


@pytest.mark.asyncio
async def test_input_normalization_behavior(db: AsyncSession, setup_api_data: dict):
    org_a = setup_api_data["org_a"]
    admin_a = setup_api_data["admin_a"]

    # Setup definitions for testing normalization
    cf_email = CustomFieldDefinition(
        organization_id=org_a.id,
        entity_type="lead",
        key="lead_email",
        label="Lead Email",
        field_type="text",
        validation_rules={"format": "email"},
        created_by=admin_a.id,
        is_active=True
    )
    cf_phone = CustomFieldDefinition(
        organization_id=org_a.id,
        entity_type="lead",
        key="lead_phone",
        label="Lead Phone",
        field_type="text",
        validation_rules={"format": "phone"},
        created_by=admin_a.id,
        is_active=True
    )
    cf_text = CustomFieldDefinition(
        organization_id=org_a.id,
        entity_type="lead",
        key="company_desc",
        label="Company Description",
        field_type="text",
        created_by=admin_a.id,
        is_active=True
    )
    db.add_all([cf_email, cf_phone, cf_text])
    await db.flush()
    await db.commit()

    definitions = [cf_email, cf_phone, cf_text]

    # Raw un-normalized payload
    raw_payload = {
        "lead_email": "  USER@TenantDomain.com   ",
        "lead_phone": " +1 (555) 019-2831 ",
        "company_desc": "   A premium enterprise solution provider.   "
    }

    # Run validation engine
    sanitized = await MetadataValidationEngine.validate_and_sanitize(
        db, Lead, org_a.id, definitions, raw_payload
    )

    # Assert normalized values
    assert sanitized["lead_email"] == "user@tenantdomain.com"
    assert sanitized["lead_phone"] == "+15550192831"
    assert sanitized["company_desc"] == "A premium enterprise solution provider."

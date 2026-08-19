import pytest
import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import Pipeline, PipelineStage
from app.models.custom_field_definition import CustomFieldDefinition
from app.services.custom_field_service import CustomFieldService
from app.services.pipeline_service import (
    create_pipeline, update_pipeline, delete_pipeline, list_pipelines,
    create_stage, update_stage, delete_stage, reorder_stages
)
from app.services.metadata_validation_engine import MetadataValidationEngine, MetadataValidationError
from app.services.metadata_cache_service import MetadataCacheService


@pytest.fixture
async def setup_test_orgs(db: AsyncSession):
    # Create two isolated organizations
    org_a = Organization(name="Tenant A", slug="tenant-a")
    org_b = Organization(name="Tenant B", slug="tenant-b")
    db.add_all([org_a, org_b])
    await db.flush()

    # Create admin for Org A
    admin_a = User(
        organization_id=org_a.id,
        email="admin_a@tenant-a.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )
    # Create employee for Org A
    employee_a = User(
        organization_id=org_a.id,
        email="emp_a@tenant-a.com",
        hashed_password="hash",
        role="Employee",
        is_active=True
    )
    # Create admin for Org B
    admin_b = User(
        organization_id=org_b.id,
        email="admin_b@tenant-b.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )
    db.add_all([admin_a, employee_a, admin_b])
    await db.flush()
    await db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "employee_a": employee_a,
        "admin_b": admin_b
    }


@pytest.mark.asyncio
async def test_multi_tenant_isolation_and_permissions(db: AsyncSession, setup_test_orgs: dict):
    org_a = setup_test_orgs["org_a"]
    org_b = setup_test_orgs["org_b"]
    admin_a = setup_test_orgs["admin_a"]
    employee_a = setup_test_orgs["employee_a"]
    admin_b = setup_test_orgs["admin_b"]

    cf_service = CustomFieldService(db)

    # 1. Non-admin roles (Employee) are rejected from creating custom fields
    with pytest.raises(HTTPException) as exc_info:
        await cf_service.create_definition(employee_a, {"key": "interest", "label": "Interest"})
    assert exc_info.value.status_code == 403

    # 2. Admin of Org A can create a custom field
    cf_a = await cf_service.create_definition(admin_a, {
        "key": "contract_val",
        "label": "Contract Value",
        "field_type": "number"
    }, entity_type="lead")
    await db.commit()

    # 3. Admin of Org B cannot access or update Org A's custom field
    with pytest.raises(HTTPException) as exc_info:
        await cf_service.update_definition(admin_b, cf_a.id, {"label": "Hacked Label"})
    assert exc_info.value.status_code == 404

    # 4. Same for pipelines
    p_a = await create_pipeline(db, admin_a, {"name": "Sales A"})
    await db.commit()

    # Org B admin cannot update Org A pipeline
    with pytest.raises(HTTPException) as exc_info:
        await update_pipeline(db, admin_b, p_a.id, {"name": "Hacked Pipeline"})
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_metadata_caching_invalidation(db: AsyncSession, setup_test_orgs: dict):
    org_a = setup_test_orgs["org_a"]
    admin_a = setup_test_orgs["admin_a"]

    cf_service = CustomFieldService(db)

    # Invalidate cache initially
    await MetadataCacheService.invalidate_custom_fields(org_a.id, "lead")
    await MetadataCacheService.invalidate_pipelines(org_a.id)

    # 1. Verification of caching custom fields on list
    cf_list = await cf_service.list_definitions(admin_a, "lead")
    cached_cfs = await MetadataCacheService.get_custom_fields(org_a.id, "lead")
    assert cached_cfs is not None
    assert len(cached_cfs) == len(cf_list)

    # 2. Invalidation on create
    await cf_service.create_definition(admin_a, {
        "key": "budget",
        "label": "Budget",
        "field_type": "number"
    }, entity_type="lead")
    cached_cfs = await MetadataCacheService.get_custom_fields(org_a.id, "lead")
    assert cached_cfs is None  # Cache cleared immediately!

    # 3. Verification of caching pipelines
    p_list = await list_pipelines(db, admin_a)
    cached_p = await MetadataCacheService.get_pipelines(org_a.id)
    assert cached_p is not None

    # Invalidation on update
    # Need to query/create dynamic pipeline first
    p_new = await create_pipeline(db, admin_a, {"name": "Secondary Pipeline"})
    cached_p = await MetadataCacheService.get_pipelines(org_a.id)
    assert cached_p is None  # Cache cleared on pipeline create!


@pytest.mark.asyncio
async def test_metadata_validation_engine_rules(db: AsyncSession, setup_test_orgs: dict):
    org_a = setup_test_orgs["org_a"]
    admin_a = setup_test_orgs["admin_a"]

    cf_service = CustomFieldService(db)

    # Create definitions
    # 1. Text field with length & regex check
    cf_text = await cf_service.create_definition(admin_a, {
        "key": "vip_code",
        "label": "VIP Code",
        "field_type": "text",
        "validation_rules": {"min_length": 3, "max_length": 6, "pattern": "^VIP-[0-9]+$"}
    }, entity_type="lead")

    # 2. Number field with bounds
    # NOTE: key changed from "score" → "credit_score" in Phase 4.1. "score" is a
    # real first-class Lead column and is now a reserved custom-field key (G3), so
    # a custom field may no longer shadow it. The test's intent (numeric min/max
    # bounds) is unchanged; the key choice was incidental.
    cf_num = await cf_service.create_definition(admin_a, {
        "key": "credit_score",
        "label": "Lead Score",
        "field_type": "number",
        "validation_rules": {"min_value": 0, "max_value": 100}
    }, entity_type="lead")

    # 3. Date field
    cf_date = await cf_service.create_definition(admin_a, {
        "key": "scheduled_date",
        "label": "Scheduled Date",
        "field_type": "date"
    }, entity_type="lead")

    # 4. Select options field
    cf_select = await cf_service.create_definition(admin_a, {
        "key": "tier",
        "label": "Customer Tier",
        "field_type": "select",
        "options": ["Gold", "Silver", "Bronze"]
    }, entity_type="lead")

    # 5. Checkbox with default value
    cf_check = await cf_service.create_definition(admin_a, {
        "key": "marketing_opt_in",
        "label": "Opt In",
        "field_type": "checkbox",
        "default_value": True
    }, entity_type="lead")

    # 6. Unique validation field
    cf_unique = await cf_service.create_definition(admin_a, {
        "key": "unique_id",
        "label": "Unique ID",
        "field_type": "text",
        "validation_rules": {"unique": True}
    }, entity_type="lead")

    await db.commit()

    definitions = [cf_text, cf_num, cf_date, cf_select, cf_check, cf_unique]

    # --- Test Passing Case ---
    payload = {
        "vip_code": "VIP-12",
        "credit_score": 45,
        "scheduled_date": "2026-08-04",
        "tier": "Gold",
        "unique_id": "U-999"
    }
    sanitized = await MetadataValidationEngine.validate_and_sanitize(
        db, Lead, org_a.id, definitions, payload
    )
    assert sanitized["vip_code"] == "VIP-12"
    assert sanitized["credit_score"] == 45
    assert sanitized["marketing_opt_in"] is True  # Injected default value!

    # --- Test Failing Pattern Case ---
    payload_bad_pattern = {"vip_code": "BAD-12"}
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(
            db, Lead, org_a.id, definitions, payload_bad_pattern
        )

    # --- Test Failing Min/Max Score Case ---
    payload_bad_score = {"credit_score": 150}
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(
            db, Lead, org_a.id, definitions, payload_bad_score
        )

    # --- Test Failing Date Format Case ---
    payload_bad_date = {"scheduled_date": "04-08-2026"}
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(
            db, Lead, org_a.id, definitions, payload_bad_date
        )

    # --- Test Reject Unknown Keys ---
    payload_unknown = {"hacked_key": "any"}
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(
            db, Lead, org_a.id, definitions, payload_unknown
        )

    # --- Test Uniqueness Validation ---
    # Create duplicate lead first
    lead_dup = Lead(
        organization_id=org_a.id,
        first_name="First",
        last_name="Last",
        title="Title",
        custom_fields={"unique_id": "U-111"},
        created_by=admin_a.id,
        stage_id=uuid.uuid4()  # Mock stage ID
    )
    db.add(lead_dup)
    await db.flush()
    await db.commit()

    # Now validate same unique value
    payload_dup = {"unique_id": "U-111"}
    with pytest.raises(MetadataValidationError) as exc:
        await MetadataValidationEngine.validate_and_sanitize(
            db, Lead, org_a.id, definitions, payload_dup
        )
    assert "already in use" in str(exc.value)


@pytest.mark.asyncio
async def test_pipeline_and_stage_deletion_dependencies(db: AsyncSession, setup_test_orgs: dict):
    org_a = setup_test_orgs["org_a"]
    admin_a = setup_test_orgs["admin_a"]

    # Create dynamic pipelines
    p_primary = await create_pipeline(db, admin_a, {"name": "Sales Primary", "is_default": True})
    p_secondary = await create_pipeline(db, admin_a, {"name": "Sales Secondary"})
    await db.commit()

    # Add stages to pipelines
    stage_primary = await create_stage(db, org_a.id, {"name": "New", "pipeline_id": p_primary.id})
    stage_secondary = await create_stage(db, org_a.id, {"name": "Interested", "pipeline_id": p_secondary.id})
    await db.commit()

    # Create lead referencing secondary pipeline
    lead = Lead(
        organization_id=org_a.id,
        first_name="Target",
        last_name="Lead",
        title="Software Engineer",
        pipeline_id=p_secondary.id,
        stage_id=stage_secondary.id,
        created_by=admin_a.id
    )
    db.add(lead)
    await db.flush()
    await db.commit()

    # 1. Deleting secondary pipeline must FAIL due to active leads reference
    with pytest.raises(HTTPException) as exc_info:
        await delete_pipeline(db, admin_a, p_secondary.id)
    assert exc_info.value.status_code == 400
    assert "active lead" in exc_info.value.detail

    # 2. Deleting secondary pipeline with REASSIGNMENT to primary succeeds
    await delete_pipeline(db, admin_a, p_secondary.id, reassignment_pipeline_id=p_primary.id)
    await db.commit()

    # Refresh lead and assert it has been mapped to primary pipeline and its default stage
    await db.refresh(lead)
    assert lead.pipeline_id == p_primary.id
    assert lead.stage_id == stage_primary.id

    # Verify secondary pipeline and its stage are soft-deleted/inactive
    await db.refresh(p_secondary)
    await db.refresh(stage_secondary)
    assert p_secondary.is_deleted is True
    assert p_secondary.is_active is False
    assert stage_secondary.is_deleted is True
    assert stage_secondary.is_active is False

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.custom_field_definition import CustomFieldDefinition
from app.models.pipeline import Pipeline, PipelineStage
from app.core.security import create_access_token
from app.core.context import mask_phone_ctx


@pytest.fixture
async def setup_leads_data(db: AsyncSession):
    # Create org
    org = Organization(name="Leads Org", slug="leads-org", metadata_version=1)
    db.add(org)
    await db.flush()

    # Create admin
    admin = User(
        organization_id=org.id,
        email="admin_leads@org.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )
    db.add(admin)
    await db.flush()

    # Create default pipeline and stage (mandatory for leads)
    pipeline = Pipeline(
        organization_id=org.id,
        name="Lead Test Pipeline",
        is_default=True,
        is_active=True
    )
    db.add(pipeline)
    await db.flush()

    stage = PipelineStage(
        organization_id=org.id,
        pipeline_id=pipeline.id,
        name="Fresh Leads",
        order_position=1,
        is_system_default=True
    )
    db.add(stage)
    await db.flush()
    await db.commit()

    token = create_access_token(admin.id)
    return {
        "org": org,
        "admin": admin,
        "stage": stage,
        "headers": {"Authorization": f"Bearer {token}"}
    }


@pytest.mark.asyncio
async def test_lead_creation_and_validation(client: AsyncClient, setup_leads_data: dict, db: AsyncSession):
    data = setup_leads_data
    org = data["org"]
    admin = data["admin"]

    # 1. Define custom fields
    cf_score = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="score_override",
        label="Score Override",
        field_type="number",
        validation_rules={"min_value": 0, "max_value": 100},
        created_by=admin.id,
        is_active=True
    )
    cf_url = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="profile_url",
        label="Profile URL",
        field_type="text",
        validation_rules={"min_length": 5},
        created_by=admin.id,
        is_active=True
    )
    db.add_all([cf_score, cf_url])
    await db.commit()

    # Create lead with valid fields
    payload_valid = {
        "last_name": "Smith",
        "title": "Lead Dev",
        "custom_fields": {
            "score_override": 75,
            "profile_url": "  https://github.com/alice  "  # leading/trailing spaces to test normalization
        }
    }
    resp = await client.post("/api/v1/leads/", json=payload_valid, headers=data["headers"])
    assert resp.status_code == 201
    lead_res = resp.json()
    assert lead_res["custom_fields"]["score_override"] == 75
    assert lead_res["custom_fields"]["profile_url"] == "https://github.com/alice"  # Normalized/trimmed!

    # Create lead with invalid fields (e.g. out of range score)
    payload_invalid = {
        "last_name": "Doe",
        "title": "Junior Dev",
        "custom_fields": {
            "score_override": 150
        }
    }
    resp = await client.post("/api/v1/leads/", json=payload_invalid, headers=data["headers"])
    assert resp.status_code == 400
    assert "must be at most 100" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_lead_update_merging_and_retroactive_required(client: AsyncClient, setup_leads_data: dict, db: AsyncSession):
    data = setup_leads_data
    org = data["org"]
    admin = data["admin"]

    # 1. Create a dynamic definitions
    cf_tier = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="customer_tier",
        label="Customer Tier",
        field_type="select",
        options=["Gold", "Silver", "Bronze"],
        created_by=admin.id,
        is_active=True
    )
    cf_notes = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="notes",
        label="Internal Notes",
        field_type="text",
        created_by=admin.id,
        is_active=True
    )
    db.add_all([cf_tier, cf_notes])
    await db.commit()

    # 2. Create lead initially
    lead = Lead(
        organization_id=org.id,
        first_name="John",
        last_name="Doe",
        title="CEO",
        stage_id=data["stage"].id,
        created_by=admin.id,
        custom_fields={"customer_tier": "Silver"}
    )
    db.add(lead)
    await db.commit()

    # 3. Patch update lead custom fields
    patch_payload = {
        "custom_fields": {
            "notes": "Interested in premium plan"
        }
    }
    resp = await client.patch(f"/api/v1/leads/{lead.id}", json=patch_payload, headers=data["headers"])
    assert resp.status_code == 200
    lead_res = resp.json()
    # Verify that the tier was preserved (merged) and internal notes added
    assert lead_res["custom_fields"]["customer_tier"] == "Silver"
    assert lead_res["custom_fields"]["notes"] == "Interested in premium plan"

    # 4. Clean/Delete non-required custom field by setting to None/""
    patch_delete_notes = {
        "custom_fields": {
            "notes": None
        }
    }
    resp = await client.patch(f"/api/v1/leads/{lead.id}", json=patch_delete_notes, headers=data["headers"])
    assert resp.status_code == 200
    lead_res = resp.json()
    assert "notes" not in lead_res["custom_fields"]

    # 5. Test Retroactive Required Field: Make customer_tier required in definitions
    cf_tier.validation_rules = {"required": True}
    db.add(cf_tier)
    await db.commit()

    from app.services.metadata_cache_service import MetadataCacheService
    await MetadataCacheService.invalidate_custom_fields(org.id, "lead")

    # Now create another lead with empty custom_fields
    lead_no_tier = Lead(
        organization_id=org.id,
        first_name="No",
        last_name="Tier",
        title="Manager",
        stage_id=data["stage"].id,
        created_by=admin.id,
        custom_fields={}
    )
    db.add(lead_no_tier)
    await db.commit()

    # Attempting to patch any attribute of lead_no_tier (e.g. first_name) must fail because required tier is missing!
    patch_name = {
        "first_name": "Updated Name"
    }
    resp = await client.patch(f"/api/v1/leads/{lead_no_tier.id}", json=patch_name, headers=data["headers"])
    assert resp.status_code == 400
    assert "is required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_archived_custom_field_behavior(client: AsyncClient, setup_leads_data: dict, db: AsyncSession):
    data = setup_leads_data
    org = data["org"]
    admin = data["admin"]

    cf_archived = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="legacy_id",
        label="Legacy ID",
        field_type="text",
        created_by=admin.id,
        is_active=False  # Archived/Inactive field definition!
    )
    db.add(cf_archived)
    await db.commit()

    # 1. Attempting to create a lead referencing legacy_id fails with 400 Unknown Key
    payload = {
        "last_name": "Gates",
        "title": "Founder",
        "custom_fields": {
            "legacy_id": "LEG-999"
        }
    }
    resp = await client.post("/api/v1/leads/", json=payload, headers=data["headers"])
    assert resp.status_code == 400
    assert "Unknown custom field key" in resp.json()["detail"]

    # 2. Existing lead with legacy_id value can still be read
    lead = Lead(
        organization_id=org.id,
        first_name="Legacy",
        last_name="Record",
        title="Admin",
        stage_id=data["stage"].id,
        created_by=admin.id,
        custom_fields={"legacy_id": "LEG-999"}
    )
    db.add(lead)
    await db.commit()

    resp = await client.get(f"/api/v1/leads/{lead.id}", headers=data["headers"])
    assert resp.status_code == 200
    assert resp.json()["custom_fields"]["legacy_id"] == "LEG-999"


@pytest.mark.asyncio
async def test_privacy_masking_integration(client: AsyncClient, setup_leads_data: dict, db: AsyncSession):
    data = setup_leads_data
    org = data["org"]
    admin = data["admin"]

    # 1. Create a custom field that maps to a phone number
    cf_phone = CustomFieldDefinition(
        organization_id=org.id,
        entity_type="lead",
        key="alternative_phone",
        label="Alternative Phone",
        field_type="text",
        validation_rules={"format": "phone"},
        created_by=admin.id,
        is_active=True
    )
    db.add(cf_phone)
    await db.commit()

    # 2. Create parent employee and reporting employee to trigger mask_phone = True
    parent_emp = User(
        organization_id=org.id,
        email="parent_emp@org.com",
        hashed_password="hash",
        role="Employee",
        is_active=True
    )
    db.add(parent_emp)
    await db.flush()

    telecaller_emp = User(
        organization_id=org.id,
        email="telecaller_emp@org.com",
        hashed_password="hash",
        role="Employee",
        reporting_to_id=parent_emp.id,
        is_active=True
    )
    db.add(telecaller_emp)
    await db.flush()

    # 3. Create lead with alternate phone assigned to telecaller_emp
    lead = Lead(
        organization_id=org.id,
        first_name="Mister",
        last_name="Masked",
        title="CTO",
        phone="+919876543210",
        stage_id=data["stage"].id,
        created_by=admin.id,
        assigned_user_id=telecaller_emp.id,
        custom_fields={"alternative_phone": "+919876543210"}
    )
    db.add(lead)
    await db.commit()

    token_telecaller = create_access_token(telecaller_emp.id)
    headers_telecaller = {"Authorization": f"Bearer {token_telecaller}"}

    # 4. Read lead under standard unmasked context (Admin)
    resp = await client.get(f"/api/v1/leads/{lead.id}", headers=data["headers"])
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["phone"] == "+919876543210"
    assert res_data["custom_fields"]["alternative_phone"] == "+919876543210"

    # 5. Read lead under masked context (Telecaller reporting to Employee)
    resp = await client.get(f"/api/v1/leads/{lead.id}", headers=headers_telecaller)
    assert resp.status_code == 200
    res_data = resp.json()
    # Verify alternative_phone key is masked just like phone!
    assert res_data["phone"] != "+919876543210"
    assert res_data["custom_fields"]["alternative_phone"] != "+919876543210"
    assert "*" in res_data["custom_fields"]["alternative_phone"]

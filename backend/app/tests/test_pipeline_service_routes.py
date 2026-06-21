import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import PipelineStage
from app.models.lead import Lead
from app.services import pipeline_service
from app.core.exceptions import PipelineStageValidationError, PipelineStageDeletionError
from app.schemas.pipeline import PipelineStageCreate, PipelineStageUpdate

@pytest.fixture
async def setup_pipeline_test_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Tenant A and Tenant B
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Users for Tenant A
    admin_a = await user_repo.create_user(org_a.id, {
        "email": "admin_a@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    manager_a = await user_repo.create_user(org_a.id, {
        "email": "manager_a@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "A",
        "role": "Manager",
        "is_active": True
    })
    employee_a = await user_repo.create_user(org_a.id, {
        "email": "employee_a@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Employee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })

    # 3. User for Tenant B
    admin_b = await user_repo.create_user(org_b.id, {
        "email": "admin_b@tenant-b.com",
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

    # Retrieve Org A seeded stages
    stages_a_res = await db.execute(
        select(PipelineStage)
        .filter(PipelineStage.organization_id == org_a.id, PipelineStage.is_deleted == False)
        .order_by(PipelineStage.order_position)
    )
    stages_a = list(stages_a_res.scalars().all())

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
        "stages_a": stages_a
    }

@pytest.mark.asyncio
async def test_create_stage_service_validation(db: AsyncSession, setup_pipeline_test_data: dict):
    data = setup_pipeline_test_data
    org_id = data["org_a"].id

    # 1. Create stage with auto-incrementing order position
    new_stage = await pipeline_service.create_stage(
        db, org_id, {"name": "Qualified", "order_position": None, "is_system_default": False}
    )
    await db.commit()
    assert new_stage.order_position == 6  # Seeded has 5 stages (positions 1..5)
    assert new_stage.name == "Qualified"

    # 2. Reject duplicate stage name
    with pytest.raises(PipelineStageValidationError) as exc:
        await pipeline_service.create_stage(
            db, org_id, {"name": "Qualified", "order_position": None}
        )
    assert "already exists in this organization" in str(exc.value)

    # 3. Reject duplicate explicit order position
    with pytest.raises(PipelineStageValidationError) as exc:
        await pipeline_service.create_stage(
            db, org_id, {"name": "Another Name", "order_position": 6}
        )
    assert "already exists" in str(exc.value)

    # 4. Swap system default stage
    new_default = await pipeline_service.create_stage(
        db, org_id, {"name": "Incoming", "order_position": None, "is_system_default": True}
    )
    await db.commit()
    
    assert new_default.is_system_default is True
    # Verify that the original default stage is no longer system default
    stages_res = await db.execute(
        select(PipelineStage).filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
    )
    stages = stages_res.scalars().all()
    defaults = [s for s in stages if s.is_system_default]
    assert len(defaults) == 1
    assert defaults[0].id == new_default.id

@pytest.mark.asyncio
async def test_reorder_stages_service_validation(db: AsyncSession, setup_pipeline_test_data: dict):
    data = setup_pipeline_test_data
    org_id = data["org_a"].id
    stages = data["stages_a"]

    # 1. Reorder positions (Swap positions of stage 0 and stage 1: 1 -> 2, 2 -> 1)
    reorder_list = [
        {"stage_id": stages[0].id, "new_position": 2},
        {"stage_id": stages[1].id, "new_position": 1}
    ]
    reordered = await pipeline_service.reorder_stages(db, org_id, reorder_list)
    await db.commit()

    # Reordered list should be returned sorted by position
    assert reordered[0].id == stages[1].id
    assert reordered[0].order_position == 1
    assert reordered[1].id == stages[0].id
    assert reordered[1].order_position == 2

    # 2. Reject duplicate positions in reorder
    with pytest.raises(PipelineStageValidationError) as exc:
        await pipeline_service.reorder_stages(
            db, org_id, [
                {"stage_id": stages[0].id, "new_position": 3},
                {"stage_id": stages[2].id, "new_position": 3}
            ]
        )
    assert "Duplicate order position detected" in str(exc.value)

    # 3. Reject stage from another organization
    with pytest.raises(PipelineStageValidationError) as exc:
        await pipeline_service.reorder_stages(
            db, org_id, [{"stage_id": uuid.uuid4(), "new_position": 10}]
        )
    assert "not found in this organization" in str(exc.value)

@pytest.mark.asyncio
async def test_delete_stage_service_validation(db: AsyncSession, setup_pipeline_test_data: dict):
    data = setup_pipeline_test_data
    org_id = data["org_a"].id
    stages = data["stages_a"]

    # Original default stage is index 0 ("Fresh Leads")
    default_stage = stages[0]
    other_stage = stages[1]  # "Contacted"
    third_stage = stages[2]  # "Followup"

    # 1. Reject deletion of default stage
    with pytest.raises(PipelineStageValidationError) as exc:
        await pipeline_service.delete_stage(db, org_id, default_stage.id)
    assert "Cannot delete the system default stage" in str(exc.value)

    # 2. Create active leads in other_stage
    lead = Lead(
        organization_id=org_id,
        first_name="Active",
        last_name="Lead",
        email="pipeline_test@org.com",
        title="Software Deal",
        stage_id=other_stage.id,
        created_by=data["admin_a"].id
    )
    db.add(lead)
    await db.commit()

    # 3. Reject deletion of other_stage because it contains active leads (no fallback provided)
    with pytest.raises(PipelineStageDeletionError) as exc:
        await pipeline_service.delete_stage(db, org_id, other_stage.id)
    assert "contains 1 active lead(s)" in str(exc.value)

    # 4. Successfully delete stage with fallback stage provided
    await pipeline_service.delete_stage(db, org_id, other_stage.id, fallback_stage_id=third_stage.id)
    await db.commit()

    # Verify lead was moved to fallback stage
    await db.refresh(lead)
    assert lead.stage_id == third_stage.id

    # Verify stage was soft-deleted (is_deleted = True)
    await db.refresh(other_stage)
    assert other_stage.is_deleted is True
    assert "deleted" in other_stage.name
    assert other_stage.order_position < 0

@pytest.mark.asyncio
async def test_pipeline_endpoints_rbac_and_isolation(client: AsyncClient, setup_pipeline_test_data: dict, db: AsyncSession):
    data = setup_pipeline_test_data
    stages = data["stages_a"]

    # 1. Active Employee can read/list stages
    resp = await client.get("/api/v1/pipelines/", headers=data["headers_employee_a"])
    assert resp.status_code == 200
    assert len(resp.json()) == 5

    # 2. Active Employee cannot create stage
    payload_create = {"name": "Rejected Stage"}
    resp = await client.post("/api/v1/pipelines/", json=payload_create, headers=data["headers_employee_a"])
    assert resp.status_code == 403

    # 3. OrgAdmin can create stage
    resp = await client.post("/api/v1/pipelines/", json={"name": "OrgAdmin Stage"}, headers=data["headers_admin_a"])
    assert resp.status_code == 201
    created_stage_id = resp.json()["id"]

    # 4. Manager can update stage properties
    resp = await client.patch(f"/api/v1/pipelines/{created_stage_id}", json={"name": "Manager Updated Name"}, headers=data["headers_manager_a"])
    assert resp.status_code == 200
    assert resp.json()["name"] == "Manager Updated Name"

    # 5. Tenant Isolation: Admin B cannot reorder or delete Tenant A stages
    reorder_payload = {"orders": [{"stage_id": str(stages[0].id), "new_position": 1}]}
    resp = await client.post("/api/v1/pipelines/reorder", json=reorder_payload, headers=data["headers_admin_b"])
    # Validation error because stages[0] is not found in Org B
    assert resp.status_code == 400
    assert "not found in this organization" in resp.json()["detail"]

    # Admin B cannot delete Tenant A stage
    resp = await client.delete(f"/api/v1/pipelines/{created_stage_id}", headers=data["headers_admin_b"])
    assert resp.status_code == 400
    assert "Target pipeline stage not found" in resp.json()["detail"]

    # 6. Admin A can delete the newly created stage
    resp = await client.delete(f"/api/v1/pipelines/{created_stage_id}", headers=data["headers_admin_a"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

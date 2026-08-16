import uuid
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select
from fastapi import HTTPException

from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.company import Company
from app.models.user import User
from app.repositories.base import TenantRepository
from app.repositories.lead_repository import LeadRepository
from app.services.lead_service import LeadService
from app.core.tenant_context import TenantContext, TenantContextError


@pytest.fixture
async def setup_isolation(db: AsyncSession):
    from app.repositories.organization import OrganizationRepository
    from app.repositories.user_repository import UserRepository
    from app.core.security import get_password_hash

    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Org A
    org_a = await org_repo.create({"name": "Org A", "slug": "org-a"})
    await db.flush()
    admin_a = await user_repo.create_user(org_a.id, {
        "email": "admin@org-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.flush()
    stage_a = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org_a.id,
        PipelineStage.is_system_default == True
    ))).scalars().first()

    # Org B
    org_b = await org_repo.create({"name": "Org B", "slug": "org-b"})
    await db.flush()
    admin_b = await user_repo.create_user(org_b.id, {
        "email": "admin@org-b.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.flush()
    stage_b = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org_b.id,
        PipelineStage.is_system_default == True
    ))).scalars().first()

    await db.commit()

    return {
        "org_a": org_a,
        "admin_a": admin_a,
        "stage_a": stage_a,
        "org_b": org_b,
        "admin_b": admin_b,
        "stage_b": stage_b
    }


# --- Test 15: TenantRepository with non-tenant model ---
def test_tenant_repository_with_non_tenant_model(db: AsyncSession):
    class NonTenantModel:
        id = None

    with pytest.raises(TypeError) as excinfo:
        TenantRepository(NonTenantModel, db, uuid.uuid4())
    assert "does not have an 'organization_id' attribute" in str(excinfo.value)


@pytest.mark.asyncio
async def test_tenant_repository_isolation_boundary(db: AsyncSession, setup_isolation: dict):
    # Setup two isolated organizations
    org_a_id = setup_isolation["org_a"].id
    org_b_id = setup_isolation["org_b"].id
    
    # Resolve users
    actor_a = setup_isolation["admin_a"]
    actor_b = setup_isolation["admin_b"]

    stage_a = setup_isolation["stage_a"]
    stage_b = setup_isolation["stage_b"]

    # 1. Tenant context exists
    token = TenantContext.set_tenant_id(org_a_id)
    assert TenantContext.get_tenant_id() == org_a_id
    TenantContext.reset_tenant_id(token)

    # 2. Tenant context missing fails closed
    with pytest.raises(TenantContextError):
        TenantContext.get_tenant_id()

    # Create repositories for org A and B
    repo_a = LeadRepository(db, org_a_id)
    repo_b = LeadRepository(db, org_b_id)

    # Create Lead in Tenant A
    lead_a = await repo_a.create({
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@org-a.com",
        "title": "Lead from Org A",
        "status": "new",
        "source": "Website",
        "created_by": actor_a.id,
        "stage_id": stage_a.id
    })
    assert lead_a.organization_id == org_a_id

    # Create Lead in Tenant B
    lead_b = await repo_b.create({
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@org-b.com",
        "title": "Lead from Org B",
        "status": "new",
        "source": "Website",
        "created_by": actor_b.id,
        "stage_id": stage_b.id
    })
    assert lead_b.organization_id == org_b_id

    # 3. Tenant A can read A's records
    fetched_a = await repo_a.get(lead_a.id)
    assert fetched_a is not None
    assert fetched_a.id == lead_a.id

    # 4. Tenant A cannot read B's records (get B -> returns None)
    fetched_b_by_a = await repo_a.get(lead_b.id)
    assert fetched_b_by_a is None

    # 5. Tenant A cannot update B's records
    with pytest.raises(ValueError) as excinfo:
        await repo_a.update(lead_b, {"title": "Hacked"})
    assert "Cross-tenant database modification blocked" in str(excinfo.value)

    # 6. Tenant A cannot delete B's records
    deleted_b_by_a = await repo_a.remove(lead_b.id)
    assert deleted_b_by_a is None
    # Verify B record is still active (not soft deleted)
    db.add(lead_b)
    await db.refresh(lead_b)
    assert lead_b.is_deleted is False

    # 7. Tenant A list only returns A records
    leads_list_a = await repo_a.get_multi()
    assert len(leads_list_a) > 0
    for l in leads_list_a:
        assert l.organization_id == org_a_id
        assert l.id != lead_b.id

    # 8. Tenant A search only returns A records
    leads_search_a, total = await repo_a.paginate_leads(search_query="Doe")
    assert len(leads_search_a) > 0
    for l in leads_search_a:
        assert l.organization_id == org_a_id
        assert l.id != lead_b.id

    # 9. Tenant A bulk operation cannot modify B records
    leads_for_update = await repo_a.get_leads_for_update([lead_a.id, lead_b.id])
    # Should only return A's lead since B's lead is filtered out by TenantRepository scoping
    assert len(leads_for_update) == 1
    assert leads_for_update[0].id == lead_a.id

    # 13. Tenant mutation protection
    with pytest.raises(ValueError) as excinfo:
        await repo_a.update(lead_a, {"organization_id": org_b_id})
    assert "Mutation of organization_id is not allowed" in str(excinfo.value)

    # 14. Create tenant override protection
    with pytest.raises(ValueError) as excinfo:
        await repo_a.create({
            "first_name": "Jack",
            "last_name": "Doe",
            "email": "jack.doe@org-a.com",
            "title": "Lead attempting override",
            "organization_id": org_b_id,
            "created_by": actor_a.id,
            "stage_id": stage_a.id
        })
    assert "Override of organization_id is not allowed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_tenant_context_relationship_validation(db: AsyncSession, setup_isolation: dict):
    org_a_id = setup_isolation["org_a"].id
    org_b_id = setup_isolation["org_b"].id
    
    actor_a = setup_isolation["admin_a"]
    actor_b = setup_isolation["admin_b"]

    # 10 & 16: Relationship lookup cannot cross tenant boundary
    stage_b = setup_isolation["stage_b"]
    
    assert stage_b is not None

    service_a = LeadService(db, org_a_id)

    # Attempt to create a Lead under Tenant A but specifying Tenant B's stage_id -> should raise 400 Bad Request
    with pytest.raises(HTTPException) as excinfo:
        await service_a.create_lead(actor_a, {
            "first_name": "RelTest",
            "last_name": "Doe",
            "email": "rel.test@org-a.com",
            "title": "Cross tenant stage test",
            "stage_id": stage_b.id
        })
    assert excinfo.value.status_code == 400
    assert "stage_id not found in your organization" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_tenant_background_task_context(db: AsyncSession, setup_isolation: dict):
    # 11. Background task context explicitly scoped
    org_a_id = setup_isolation["org_a"].id
    actor_a = setup_isolation["admin_a"]
    stage_a = setup_isolation["stage_a"]
    
    token = TenantContext.set_tenant_id(org_a_id)
    try:
        repo = LeadRepository(db, TenantContext.get_tenant_id())
        lead = await repo.create({
            "first_name": "Bg",
            "last_name": "Task",
            "email": "bg.task@org-a.com",
            "title": "Background Job Lead",
            "created_by": actor_a.id,
            "stage_id": stage_a.id
        })
        assert lead.organization_id == org_a_id
    finally:
        TenantContext.reset_tenant_id(token)


@pytest.mark.asyncio
async def test_tenant_concurrent_context_leakage(db: AsyncSession, setup_isolation: dict):
    # 12 & 17. Concurrent async requests do not leak context
    org_a_id = setup_isolation["org_a"].id
    org_b_id = setup_isolation["org_b"].id
    
    actor_a = setup_isolation["admin_a"]
    actor_b = setup_isolation["admin_b"]

    stage_a = setup_isolation["stage_a"]
    stage_b = setup_isolation["stage_b"]

    session_maker = async_sessionmaker(bind=db.bind, class_=AsyncSession, expire_on_commit=False)

    async def run_scoped_flow(org_id: uuid.UUID, first_name: str, creator_id: uuid.UUID, stage_id: uuid.UUID):
        # We explicitly bind context variables inside each concurrent coroutine
        token = TenantContext.set_tenant_id(org_id)
        async with session_maker() as session:
            try:
                repo = LeadRepository(session, TenantContext.get_tenant_id())
                # Simulate yield to allow context switching
                await asyncio.sleep(0.01)
                # Query something
                lead = await repo.create({
                    "first_name": first_name,
                    "last_name": "Concurrent",
                    "email": f"{first_name}@test.com",
                    "title": f"Concurrent lead for {org_id}",
                    "created_by": creator_id,
                    "stage_id": stage_id
                })
                # Simulate another yield
                await asyncio.sleep(0.01)
                assert TenantContext.get_tenant_id() == org_id
                assert lead.organization_id == org_id
                await session.commit()
                return lead.id
            finally:
                TenantContext.reset_tenant_id(token)

    # Run concurrently
    res_a, res_b = await asyncio.gather(
        run_scoped_flow(org_a_id, "UserA", actor_a.id, stage_a.id),
        run_scoped_flow(org_b_id, "UserB", actor_b.id, stage_b.id)
    )

    # Clean up created records
    # Scoped repositories to clean up
    repo_a = LeadRepository(db, org_a_id)
    repo_b = LeadRepository(db, org_b_id)
    assert (await repo_a.get(res_a)) is not None
    assert (await repo_a.get(res_b)) is None
    assert (await repo_b.get(res_b)) is not None
    assert (await repo_b.get(res_a)) is None

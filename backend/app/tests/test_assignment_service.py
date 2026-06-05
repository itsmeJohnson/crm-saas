import pytest
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.assignment_service import AssignmentService

@pytest.fixture
async def assignment_setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Create Organization
    org = await org_repo.create({"name": "Test Org", "slug": "test-org"})
    await db.commit()

    # Create OrgAdmin creator
    creator = await user_repo.create_user(org.id, {
        "email": "creator@testorg.com",
        "hashed_password": "hashedpassword123",
        "first_name": "Alice",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })

    # Create active Employee A
    emp_a = await user_repo.create_user(org.id, {
        "email": "emp_a@testorg.com",
        "hashed_password": "hashedpassword123",
        "first_name": "Employee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })

    # Create active Employee B
    emp_b = await user_repo.create_user(org.id, {
        "email": "emp_b@testorg.com",
        "hashed_password": "hashedpassword123",
        "first_name": "Employee",
        "last_name": "B",
        "role": "Employee",
        "is_active": True
    })

    # Create INACTIVE Employee C (should be skipped!)
    emp_c = await user_repo.create_user(org.id, {
        "email": "emp_c@testorg.com",
        "hashed_password": "hashedpassword123",
        "first_name": "Employee",
        "last_name": "C",
        "role": "Employee",
        "is_active": False
    })
    await db.commit()

    return {
        "org": org,
        "creator": creator,
        "emp_a": emp_a,
        "emp_b": emp_b,
        "emp_c": emp_c
    }

@pytest.mark.asyncio
async def test_round_robin_distribution(db: AsyncSession, assignment_setup: dict):
    data = assignment_setup
    assign_service = AssignmentService(db)

    # Ensure config is initialized and active
    config = await assign_service.get_or_create_config(data["org"].id)
    assert config.is_active is True
    assert config.last_assigned_user_id is None

    # Lead 1 Creation
    lead1 = Lead(
        organization_id=data["org"].id,
        first_name="Lead",
        last_name="One",
        title="Software Opportunity",
        created_by=data["creator"].id
    )
    assigned_user1 = await assign_service.assign_lead(lead1)
    assert assigned_user1 is not None
    assert assigned_user1.id in [data["emp_a"].id, data["emp_b"].id]
    assert assigned_user1.id != data["emp_c"].id
    assert lead1.assigned_user_id == assigned_user1.id
    
    # Check that configuration was updated
    await db.refresh(config)
    assert config.last_assigned_user_id == assigned_user1.id

    # Lead 2 Creation (Should distribute to the OTHER active user)
    lead2 = Lead(
        organization_id=data["org"].id,
        first_name="Lead",
        last_name="Two",
        title="Hardware Opportunity",
        created_by=data["creator"].id
    )
    assigned_user2 = await assign_service.assign_lead(lead2)
    assert assigned_user2 is not None
    assert assigned_user2.id in [data["emp_a"].id, data["emp_b"].id]
    assert assigned_user2.id != assigned_user1.id # Must rotate to the other user!
    assert lead2.assigned_user_id == assigned_user2.id

    # Lead 3 Creation (Should loop back to the first user)
    lead3 = Lead(
        organization_id=data["org"].id,
        first_name="Lead",
        last_name="Three",
        title="Consulting Opportunity",
        created_by=data["creator"].id
    )
    assigned_user3 = await assign_service.assign_lead(lead3)
    assert assigned_user3 is not None
    assert assigned_user3.id == assigned_user1.id # Loops back!

@pytest.mark.asyncio
async def test_auto_assignment_disabled(db: AsyncSession, assignment_setup: dict):
    data = assignment_setup
    assign_service = AssignmentService(db)

    # Disable auto assignment
    await assign_service.toggle_assignment(data["org"].id, is_active=False)

    lead = Lead(
        organization_id=data["org"].id,
        first_name="Isolated",
        last_name="Isolated",
        title="CRM Deal",
        created_by=data["creator"].id
    )
    assigned_user = await assign_service.assign_lead(lead)
    assert assigned_user is None
    assert lead.assigned_user_id is None

import pytest
import uuid
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.services.assignment_service import AssignmentService
from app.models.user import User
from app.models.lead import Lead
from app.schemas.lead_assign import LeadBulkAssignRequest

@pytest.fixture
async def setup_hierarchy_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Hierarchy Org", "slug": "hierarchy-org"})
    await db.commit()

    # 2. Create Super Admin (OrgAdmin) - reports to None
    super_admin = await user_repo.create_user(org.id, {
        "email": "super_admin@h.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True,
        "reporting_to_id": None
    })
    await db.commit()

    # 3. Create Manager - reports to Super Admin
    manager = await user_repo.create_user(org.id, {
        "email": "manager@h.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })
    await db.commit()

    # 4. Create Team Leader (TL) - Employee reporting to Manager
    team_leader = await user_repo.create_user(org.id, {
        "email": "tl@h.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })
    await db.commit()

    # 5. Create Telecaller (Agent) - Employee reporting to TL
    telecaller = await user_repo.create_user(org.id, {
        "email": "agent@h.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": team_leader.id
    })
    await db.commit()

    token_super = create_access_token(super_admin.id)
    token_manager = create_access_token(manager.id)
    token_tl = create_access_token(team_leader.id)
    token_agent = create_access_token(telecaller.id)

    from app.models.pipeline import PipelineStage
    res = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True
        )
    )
    default_stage_id = res.scalar()

    return {
        "org": org,
        "super_admin": super_admin,
        "manager": manager,
        "team_leader": team_leader,
        "telecaller": telecaller,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "headers_manager": {"Authorization": f"Bearer {token_manager}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_agent": {"Authorization": f"Bearer {token_agent}"},
        "default_stage_id": default_stage_id
    }

@pytest.mark.asyncio
async def test_reporting_hierarchy_validations(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    manager = data["manager"]
    team_leader = data["team_leader"]
    user_service = UserService(db)

    # 1. OrgAdmin cannot report to anyone
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=None,
            role="OrgAdmin",
            reporting_to_id=manager.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "OrgAdmin cannot report to anyone" in exc.value.detail

    # 2. Manager cannot report to a non-OrgAdmin (e.g. reporting to another Manager)
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=None,
            role="Manager",
            reporting_to_id=manager.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "Managers must report to a Super Admin" in exc.value.detail

    # 3. Employee (TL) must report to a Manager, not an OrgAdmin directly
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=None,
            role="Employee",
            reporting_to_id=super_admin.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "Employees must report to either a Manager (TL) or a Team Leader" in exc.value.detail

    # 4. Telecaller reporting to an Employee who has no parent/reports to OrgAdmin (invalid)
    invalid_tl = await UserRepository(db).create_user(org.id, {
        "email": "invalid_tl@h.com",
        "hashed_password": "hash",
        "role": "Employee",
        "reporting_to_id": super_admin.id
    })
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=None,
            role="Employee",
            reporting_to_id=invalid_tl.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "Telecallers must report to a Team Leader who reports to a Manager" in exc.value.detail

@pytest.mark.asyncio
async def test_circular_dependency_validation(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    manager = data["manager"]
    team_leader = data["team_leader"]
    telecaller = data["telecaller"]
    user_service = UserService(db)

    # User cannot report to themselves
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=manager.id,
            role="Manager",
            reporting_to_id=manager.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "cannot report to themselves" in exc.value.detail

    # Circular reporting dependency: Manager cannot report to Team Leader who reports to Manager
    with pytest.raises(HTTPException) as exc:
        await user_service.validate_reporting_structure(
            user_id=manager.id,
            role="Manager",
            reporting_to_id=team_leader.id,
            organization_id=org.id
        )
    assert exc.value.status_code == 400
    assert "Circular reporting dependency detected" in exc.value.detail

@pytest.mark.asyncio
async def test_downline_membership_lookup(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    super_admin = data["super_admin"]
    manager = data["manager"]
    team_leader = data["team_leader"]
    telecaller = data["telecaller"]
    user_service = UserService(db)

    # Check downlines of Super Admin: should contain manager, team_leader, and telecaller
    super_downlines = await user_service.get_downline_user_ids(super_admin)
    assert manager.id in super_downlines
    assert team_leader.id in super_downlines
    assert telecaller.id in super_downlines

    # Check downlines of Manager: should contain team_leader and telecaller
    manager_downlines = await user_service.get_downline_user_ids(manager)
    assert team_leader.id in manager_downlines
    assert telecaller.id in manager_downlines
    assert manager.id not in manager_downlines

    # Check downlines of TL: should contain telecaller
    tl_downlines = await user_service.get_downline_user_ids(team_leader)
    assert telecaller.id in tl_downlines
    assert team_leader.id not in tl_downlines

    # Check downlines of Telecaller: empty
    agent_downlines = await user_service.get_downline_user_ids(telecaller)
    assert len(agent_downlines) == 0

@pytest.mark.asyncio
async def test_bulk_assignment_validation_permissions(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    manager = data["manager"]
    team_leader = data["team_leader"]
    telecaller = data["telecaller"]
    assignment_service = AssignmentService(db)

    # Let's create some dummy leads
    leads = []
    for i in range(5):
        lead = Lead(
            organization_id=org.id,
            first_name="Lead",
            last_name=str(i),
            title="Deal",
            created_by=super_admin.id,
            stage_id=data["default_stage_id"]
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    # Sort leads by ID to match database ordering
    leads.sort(key=lambda l: l.id)
    lead_ids = [l.id for l in leads]

    # Super Admin can assign to Manager, TL, Agent (all are downlines)
    req = LeadBulkAssignRequest(
        lead_ids=lead_ids,
        assignee_ids=[manager.id, team_leader.id],
        strategy="SPLIT"
    )
    res = await assignment_service.assign_leads_bulk(super_admin, req)
    assert res.assigned_count == 5

    # TL cannot assign to Manager (Manager is not in TL's downline)
    req_invalid = LeadBulkAssignRequest(
        lead_ids=lead_ids,
        assignee_ids=[manager.id],
        strategy="SPLIT"
    )
    with pytest.raises(HTTPException) as exc:
        await assignment_service.assign_leads_bulk(team_leader, req_invalid)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_bulk_assignment_split_and_range_strategies(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    team_leader = data["team_leader"]
    telecaller = data["telecaller"]
    assignment_service = AssignmentService(db)

    # Create 10 leads
    leads = []
    for i in range(10):
        lead = Lead(
            organization_id=org.id,
            first_name="Lead",
            last_name=str(i),
            title="Deal",
            created_by=super_admin.id,
            stage_id=data["default_stage_id"]
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    # Sort leads by ID to match database ordering
    leads.sort(key=lambda l: l.id)
    lead_ids = [l.id for l in leads]

    # Test SPLIT Strategy: 10 leads, 3 assignees (team_leader, telecaller, and let's add one more agent)
    agent2 = await UserRepository(db).create_user(org.id, {
        "email": "agent2@h.com",
        "hashed_password": "hash",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": team_leader.id
    })
    await db.commit()

    assignees = [team_leader.id, telecaller.id, agent2.id]
    
    # 1. SPLIT distribution: size 10 split by 3 assignees: 
    # sizes: 10 // 3 = 3, remainder 10 % 3 = 1. So sizes: 4, 3, 3.
    req_split = LeadBulkAssignRequest(
        lead_ids=lead_ids,
        assignee_ids=assignees,
        strategy="SPLIT"
    )
    res_split = await assignment_service.assign_leads_bulk(super_admin, req_split)
    assert res_split.assigned_count == 10

    # Verify contiguous chunks
    # Refresh leads from db
    for l in leads:
        await db.refresh(l)
    
    # Check lead 0-3 are assigned to assignees[0] (team_leader)
    for i in range(4):
        assert leads[i].assigned_user_id == assignees[0]
    # Check lead 4-6 are assigned to assignees[1] (telecaller)
    for i in range(4, 7):
        assert leads[i].assigned_user_id == assignees[1]
    # Check lead 7-9 are assigned to assignees[2] (agent2)
    for i in range(7, 10):
        assert leads[i].assigned_user_id == assignees[2]

    # 2. RANGE Strategy (Interleaved): 10 leads, 3 assignees
    req_range = LeadBulkAssignRequest(
        lead_ids=lead_ids,
        assignee_ids=assignees,
        strategy="RANGE"
    )
    res_range = await assignment_service.assign_leads_bulk(super_admin, req_range)
    assert res_range.assigned_count == 10

    # Refresh leads
    for l in leads:
        await db.refresh(l)

    # Verify interleaved assignments
    for idx, lead in enumerate(leads):
        assert lead.assigned_user_id == assignees[idx % 3]

@pytest.mark.asyncio
async def test_bulk_assignment_slicing(db: AsyncSession, setup_hierarchy_data: dict):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    team_leader = data["team_leader"]
    telecaller = data["telecaller"]
    assignment_service = AssignmentService(db)

    # Create 5 leads
    leads = []
    for i in range(5):
        lead = Lead(
            organization_id=org.id,
            first_name="Lead",
            last_name=str(i),
            title="Deal",
            created_by=super_admin.id,
            stage_id=data["default_stage_id"]
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    # Sort leads by ID to match database ordering
    leads.sort(key=lambda l: l.id)
    lead_ids = [l.id for l in leads]

    # Assign range slicing [1:4] (leads 1, 2, 3) to telecaller
    req = LeadBulkAssignRequest(
        lead_ids=lead_ids,
        assignee_ids=[telecaller.id],
        strategy="SPLIT",
        range_start=1,
        range_end=4
    )
    res = await assignment_service.assign_leads_bulk(super_admin, req)
    assert res.assigned_count == 3
    assert res.lead_ids == lead_ids[1:4]

    for i in range(5):
        await db.refresh(leads[i])
    
    assert leads[0].assigned_user_id is None
    assert leads[1].assigned_user_id == telecaller.id
    assert leads[2].assigned_user_id == telecaller.id
    assert leads[3].assigned_user_id == telecaller.id
    assert leads[4].assigned_user_id is None

@pytest.mark.asyncio
async def test_bulk_assignment_routes_api(client: AsyncClient, setup_hierarchy_data: dict, db: AsyncSession):
    data = setup_hierarchy_data
    org = data["org"]
    super_admin = data["super_admin"]
    telecaller = data["telecaller"]

    # Create 3 leads
    leads = []
    for i in range(3):
        lead = Lead(
            organization_id=org.id,
            first_name="APITesting",
            last_name=str(i),
            title="Deal",
            created_by=super_admin.id,
            stage_id=data["default_stage_id"]
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    # Sort leads by ID to match database ordering
    leads.sort(key=lambda l: l.id)
    lead_ids = [str(l.id) for l in leads]

    # POST to /api/v1/leads/assign-bulk
    payload = {
        "lead_ids": lead_ids,
        "assignee_ids": [str(telecaller.id)],
        "strategy": "SPLIT",
        "range_start": 0,
        "range_end": 2
    }
    resp = await client.post("/api/v1/leads/assign-bulk", json=payload, headers=data["headers_super"])
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["assigned_count"] == 2
    assert res_data["lead_ids"] == lead_ids[0:2]

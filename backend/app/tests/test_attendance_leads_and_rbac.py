import pytest
import uuid
from datetime import datetime, date, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.attendance import AttendanceRecord
from app.services.user_service import UserService
from app.services.lead_service import LeadService
from app.services.assignment_service import AssignmentService
from app.schemas.lead_assign import LeadBulkAssignRequest

from app.repositories.organization import OrganizationRepository
from app.models.pipeline import PipelineStage
from sqlalchemy import select

@pytest.fixture
async def setup_test_org(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    org = await org_repo.create({"name": "Test Tenant", "slug": f"test-tenant-{uuid.uuid4().hex[:6]}"})
    await db.commit()

    super_admin = User(
        organization_id=org.id,
        email=f"admin_{uuid.uuid4().hex[:6]}@tenant.com",
        hashed_password="hash",
        role="OrgAdmin",
        is_active=True
    )
    db.add(super_admin)

    manager = User(
        organization_id=org.id,
        email=f"mgr_{uuid.uuid4().hex[:6]}@tenant.com",
        hashed_password="hash",
        role="Manager",
        is_active=True,
        reporting_to_id=super_admin.id
    )
    db.add(manager)

    team_leader = User(
        organization_id=org.id,
        email=f"tl_{uuid.uuid4().hex[:6]}@tenant.com",
        hashed_password="hash",
        role="Employee",
        is_active=True,
        reporting_to_id=manager.id
    )
    db.add(team_leader)

    agent1 = User(
        organization_id=org.id,
        email=f"agent1_{uuid.uuid4().hex[:6]}@tenant.com",
        hashed_password="hash",
        role="Employee",
        is_active=True,
        reporting_to_id=team_leader.id
    )
    agent2 = User(
        organization_id=org.id,
        email=f"agent2_{uuid.uuid4().hex[:6]}@tenant.com",
        hashed_password="hash",
        role="Employee",
        is_active=True,
        reporting_to_id=team_leader.id
    )
    db.add_all([agent1, agent2])
    await db.commit()

    stage_res = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True
        )
    )
    default_stage_id = stage_res.scalar()

    return {
        "org": org,
        "super_admin": super_admin,
        "manager": manager,
        "team_leader": team_leader,
        "agent1": agent1,
        "agent2": agent2,
        "default_stage_id": default_stage_id
    }

@pytest.mark.asyncio
async def test_lead_deletion_permissions(db: AsyncSession, setup_test_org: dict):
    data = setup_test_org
    lead_service = LeadService(db, data["org"].id)

    # Create test lead
    lead = Lead(
        organization_id=data["org"].id,
        title="Delete Test Lead",
        first_name="John",
        last_name="Doe",
        stage_id=data["default_stage_id"],
        created_by=data["super_admin"].id,
        status="New"
    )
    db.add(lead)
    await db.flush()

    # 1. Telecaller / Sales Agent cannot delete lead (HTTP 403)
    with pytest.raises(HTTPException) as exc:
        await lead_service.soft_delete_lead(data["agent1"], lead.id)
    assert exc.value.status_code == 403
    assert "Only Managers and Administrators" in exc.value.detail

    # 2. Team Leader cannot delete lead (HTTP 403)
    with pytest.raises(HTTPException) as exc:
        await lead_service.soft_delete_lead(data["team_leader"], lead.id)
    assert exc.value.status_code == 403
    assert "Only Managers and Administrators" in exc.value.detail

    # 3. Manager can delete lead
    deleted = await lead_service.soft_delete_lead(data["manager"], lead.id)
    assert deleted.is_deleted is True

@pytest.mark.asyncio
async def test_attendance_aware_auto_assignment(db: AsyncSession, setup_test_org: dict):
    data = setup_test_org
    org = data["org"]
    assign_service = AssignmentService(db)
    today = datetime.now(timezone.utc).date()

    lead1 = Lead(
        organization_id=org.id,
        title="Attendance Lead 1",
        first_name="Jane",
        last_name="Smith",
        stage_id=data["default_stage_id"],
        created_by=data["super_admin"].id,
        status="New"
    )
    db.add(lead1)
    await db.flush()

    # Initially, neither agent1 nor agent2 has marked attendance.
    # Therefore, both are considered absent. Auto-assignment must return None.
    assigned = await assign_service.assign_lead(lead1)
    assert assigned is None
    assert lead1.assigned_user_id is None

    # Now agent1 clocks in (marked attendance today, status=present, clock_out_at=None)
    att1 = AttendanceRecord(
        organization_id=org.id,
        user_id=data["agent1"].id,
        work_date=today,
        clock_in_at=datetime.now(timezone.utc),
        clock_out_at=None,
        status="present"
    )
    db.add(att1)
    await db.flush()

    # Auto-assign lead1 now: agent1 is present, agent2 is absent.
    # Lead MUST be assigned to agent1.
    assigned = await assign_service.assign_lead(lead1)
    assert assigned is not None
    assert assigned.id == data["agent1"].id
    assert lead1.assigned_user_id == data["agent1"].id

    # Now agent2 also clocks in
    att2 = AttendanceRecord(
        organization_id=org.id,
        user_id=data["agent2"].id,
        work_date=today,
        clock_in_at=datetime.now(timezone.utc),
        clock_out_at=None,
        status="present"
    )
    db.add(att2)
    await db.flush()

    # Next lead should round-robin to agent2
    lead2 = Lead(
        organization_id=org.id,
        title="Attendance Lead 2",
        first_name="Bob",
        last_name="Johnson",
        stage_id=data["default_stage_id"],
        created_by=data["super_admin"].id,
        status="New"
    )
    db.add(lead2)
    await db.flush()

    assigned2 = await assign_service.assign_lead(lead2)
    assert assigned2 is not None
    assert assigned2.id == data["agent2"].id

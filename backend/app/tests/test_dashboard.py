import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import create_access_token, get_password_hash
from app.services.dashboard_service import DashboardService

@pytest.fixture
async def setup_dashboard_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Setup Org A and Org B
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # Active User in Org A
    user_a = await user_repo.create_user(org_a.id, {
        "email": "admin@tenant-a.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    # Active User in Org B
    user_b = await user_repo.create_user(org_b.id, {
        "email": "admin@tenant-b.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    token_a = create_access_token(user_a.id)
    token_b = create_access_token(user_b.id)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"}
    }

@pytest.mark.asyncio
async def test_dashboard_summary_and_tenant_isolation(client: AsyncClient, setup_dashboard_data: dict):
    data = setup_dashboard_data

    # Initial call to summary (empty state)
    response = await client.get("/api/v1/dashboard/summary", headers=data["headers_a"])
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_leads"] == 0
    assert summary["contacts_count"] == 0
    assert summary["companies_count"] == 0
    assert summary["activities_count"] == 0
    assert len(summary["leads_by_status"]) == 0
    assert len(summary["assigned_leads_breakdown"]) == 0

    # 1. Create a Company in Org A
    comp_payload = {"name": "Tenant A Corp", "domain": "tenant-a.com", "industry": "Tech"}
    response = await client.post("/api/v1/companies/", json=comp_payload, headers=data["headers_a"])
    assert response.status_code == 201

    # 2. Create a Lead in Org A
    lead_payload = {
        "title": "A Great Deal",
        "last_name": "LeadA",
        "status": "Qualified",
        "value": 150000.0,
        "assigned_user_id": str(data["user_a"].id)
    }
    response = await client.post("/api/v1/leads/", json=lead_payload, headers=data["headers_a"])
    assert response.status_code == 201

    # 3. Create an Activity in Org A
    act_payload = {
        "activity_type": "Call",
        "subject": "Introductory Call",
        "status": "Planned"
    }
    response = await client.post("/api/v1/activities/", json=act_payload, headers=data["headers_a"])
    assert response.status_code == 201

    # 4. Check dashboard summary again for Org A
    response = await client.get("/api/v1/dashboard/summary", headers=data["headers_a"])
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_leads"] == 1
    assert summary["companies_count"] == 1
    assert summary["activities_count"] == 1
    assert summary["leads_by_status"]["Qualified"] == 1
    assert len(summary["assigned_leads_breakdown"]) == 1
    assert summary["assigned_leads_breakdown"][0]["user_name"] == "Admin A"
    assert summary["assigned_leads_breakdown"][0]["lead_count"] == 1

    # 5. Check dashboard summary for Org B - should be completely isolated (all zeros)
    response = await client.get("/api/v1/dashboard/summary", headers=data["headers_b"])
    assert response.status_code == 200
    summary_b = response.json()
    assert summary_b["total_leads"] == 0
    assert summary_b["companies_count"] == 0
    assert summary_b["activities_count"] == 0
    assert len(summary_b["leads_by_status"]) == 0
    assert len(summary_b["assigned_leads_breakdown"]) == 0

@pytest.mark.asyncio
async def test_dashboard_recent_activities_pagination(client: AsyncClient, setup_dashboard_data: dict):
    data = setup_dashboard_data

    # Create 12 activities in Org A to test pagination (default limit is 10)
    for i in range(12):
        act_payload = {
            "activity_type": "Task",
            "subject": f"Task number {i}",
            "status": "Planned"
        }
        response = await client.post("/api/v1/activities/", json=act_payload, headers=data["headers_a"])
        assert response.status_code == 201

    # Get page 1
    response = await client.get("/api/v1/dashboard/recent-activities?page=1&limit=10", headers=data["headers_a"])
    assert response.status_code == 200
    activities = response.json()
    assert activities["total"] == 12
    assert len(activities["items"]) == 10
    assert activities["items"][0]["subject"] == "Task number 11" # Order by created_at desc

    # Get page 2
    response = await client.get("/api/v1/dashboard/recent-activities?page=2&limit=10", headers=data["headers_a"])
    assert response.status_code == 200
    activities_p2 = response.json()
    assert len(activities_p2["items"]) == 2


@pytest.mark.asyncio
async def test_dashboard_summary_extended_widgets(client: AsyncClient, setup_dashboard_data: dict):
    """leads_by_source, leads_by_stage, conversion_rate, and today's agenda counts."""
    data = setup_dashboard_data

    lead_payload = {
        "title": "Sourced Deal",
        "last_name": "LeadA",
        "status": "New",
        "source": "Website",
        "value": 5000.0,
    }
    response = await client.post("/api/v1/leads/", json=lead_payload, headers=data["headers_a"])
    assert response.status_code == 201

    response = await client.get("/api/v1/dashboard/summary", headers=data["headers_a"])
    assert response.status_code == 200
    summary = response.json()

    assert summary["leads_by_source"]["Website"] == 1

    # A freshly created org gets the system-default pipeline (OrganizationRepository
    # seeds a "Converted" stage at position 5), so conversion_rate is a real number
    # here — 0.0 because nothing has reached that stage yet, not None/unconfigured.
    assert summary["conversion_rate"] == 0.0
    assert isinstance(summary["leads_by_stage"], list)
    assert any(s["stage_name"] == "Converted" for s in summary["leads_by_stage"])
    assert sum(s["count"] for s in summary["leads_by_stage"]) == summary["total_leads"]

    # The lead was just created "now", so it counts toward today's agenda.
    assert summary["today"]["leads_created"] >= 1


@pytest.mark.asyncio
async def test_team_status_permissions_and_tenant_isolation(client: AsyncClient, db: AsyncSession):
    from app.repositories.organization import OrganizationRepository
    from app.repositories.user_repository import UserRepository
    from app.core.security import create_access_token, get_password_hash

    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Status Org", "slug": "status-org"})
    await db.commit()

    manager = await user_repo.create_user(org.id, {
        "email": "manager@status.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
    })
    # Team Leader = Employee reporting to a Manager.
    team_leader = await user_repo.create_user(org.id, {
        "email": "tl@status.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id,
    })
    # Telecaller = Employee reporting to another Employee (the Team Leader).
    telecaller = await user_repo.create_user(org.id, {
        "email": "tc@status.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Telecaller",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": team_leader.id,
    })
    await db.commit()

    headers_manager = {"Authorization": f"Bearer {create_access_token(manager.id)}"}
    headers_tl = {"Authorization": f"Bearer {create_access_token(team_leader.id)}"}
    headers_telecaller = {"Authorization": f"Bearer {create_access_token(telecaller.id)}"}

    # Manager sees their full recursive downline's (default IDLE) live status.
    res_manager = await client.get("/api/v1/dashboard/team-status", headers=headers_manager)
    assert res_manager.status_code == 200
    members = res_manager.json()
    assert {m["user_id"] for m in members} == {str(team_leader.id), str(telecaller.id)}
    assert all(m["state"] == "IDLE" for m in members)

    # A Team Leader is also authorized (sees their own downline: the telecaller).
    res_tl = await client.get("/api/v1/dashboard/team-status", headers=headers_tl)
    assert res_tl.status_code == 200
    assert [m["user_id"] for m in res_tl.json()] == [str(telecaller.id)]

    # A plain Telecaller (bottom of the hierarchy) is not authorized.
    res_telecaller = await client.get("/api/v1/dashboard/team-status", headers=headers_telecaller)
    assert res_telecaller.status_code == 403

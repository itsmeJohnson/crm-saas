import pytest
import uuid
from datetime import datetime, date, timezone, timedelta, time
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.pipeline import PipelineStage
from app.models.target import PerformanceTarget, TargetType, MetricType
from app.models.audit_log import AuditLog
from app.services.analytics_service import AnalyticsService

@pytest.fixture
async def setup_analytics_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Analytics Org", "slug": "analytics-org"})
    await db.commit()

    # 2. Create Super Admin (OrgAdmin)
    super_admin = await user_repo.create_user(org.id, {
        "email": "super_admin@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # 3. Create Manager
    manager = await user_repo.create_user(org.id, {
        "email": "manager@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })
    await db.commit()

    # 4. Create Team Leader (TL)
    tl = await user_repo.create_user(org.id, {
        "email": "tl@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })
    await db.commit()

    # 5. Create Telecallers (Agents) under TL
    agent1 = await user_repo.create_user(org.id, {
        "email": "agent1@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    agent2 = await user_repo.create_user(org.id, {
        "email": "agent2@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "Two",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    agent3 = await user_repo.create_user(org.id, {
        "email": "agent3@analytics.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "Three",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    await db.commit()

    # 6. Resolve auto-seeded default stages: Converted, Dropped
    stages_res = await db.execute(
        select(PipelineStage).where(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_deleted == False
        )
    )
    stages = stages_res.scalars().all()
    converted_stage = next(s for s in stages if s.name == "Converted")
    dropped_stage = next(s for s in stages if s.name == "Dropped")

    token_super = create_access_token(super_admin.id)
    token_manager = create_access_token(manager.id)
    token_tl = create_access_token(tl.id)
    token_agent1 = create_access_token(agent1.id)

    return {
        "org": org,
        "super_admin": super_admin,
        "manager": manager,
        "tl": tl,
        "agent1": agent1,
        "agent2": agent2,
        "agent3": agent3,
        "converted_stage": converted_stage,
        "dropped_stage": dropped_stage,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "headers_manager": {"Authorization": f"Bearer {token_manager}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_agent1": {"Authorization": f"Bearer {token_agent1}"}
    }

@pytest.mark.asyncio
async def test_performance_target_model(db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    org = data["org"]

    # 1. Create a performance target
    target = PerformanceTarget(
        organization_id=org.id,
        target_type=TargetType.DAILY,
        metric_type=MetricType.CALLS_MADE,
        target_value=100,
        start_date=date.today(),
        end_date=date.today()
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)

    assert target.id is not None
    assert target.target_value == 100
    assert target.target_type == TargetType.DAILY

    # 2. Retrieve
    stmt = select(PerformanceTarget).where(PerformanceTarget.id == target.id)
    res = await db.execute(stmt)
    retrieved = res.scalar()
    assert retrieved is not None
    assert retrieved.metric_type == MetricType.CALLS_MADE

@pytest.mark.asyncio
async def test_telecaller_metrics_aggregation(db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    agent1 = data["agent1"]
    conv_stage = data["converted_stage"]
    org = data["org"]

    # Seed audit logs for agent1 on today
    today = date.today()
    now_utc = datetime.combine(today, time(12, 0)).replace(tzinfo=timezone.utc)

    # Log 1: standard call (not converted)
    log1 = AuditLog(
        organization_id=org.id,
        actor_user_id=agent1.id,
        action="LEAD_DISPOSITION_SUBMITTED",
        resource_type="Lead",
        resource_id=str(uuid.uuid4()),
        action_metadata={"status": "Busy", "new_stage_id": str(uuid.uuid4())},
        created_at=now_utc
    )

    # Log 2: converted call
    log2 = AuditLog(
        organization_id=org.id,
        actor_user_id=agent1.id,
        action="LEAD_DISPOSITION_SUBMITTED",
        resource_type="Lead",
        resource_id=str(uuid.uuid4()),
        action_metadata={"status": "Picked", "new_stage_id": str(conv_stage.id)},
        created_at=now_utc
    )

    # Log 3: call from yesterday (should not be aggregated today)
    log3 = AuditLog(
        organization_id=org.id,
        actor_user_id=agent1.id,
        action="LEAD_DISPOSITION_SUBMITTED",
        resource_type="Lead",
        resource_id=str(uuid.uuid4()),
        action_metadata={"status": "Busy", "new_stage_id": str(uuid.uuid4())},
        created_at=now_utc - timedelta(days=1)
    )

    db.add_all([log1, log2, log3])
    await db.commit()

    metrics = await AnalyticsService.get_telecaller_metrics(db, agent1, today)
    assert metrics.calls_made == 2
    assert metrics.unique_leads_contacted == 2
    assert metrics.conversions == 1

@pytest.mark.asyncio
async def test_team_leader_performer_calculations(db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    tl = data["tl"]
    agent1 = data["agent1"]
    agent2 = data["agent2"]
    agent3 = data["agent3"]
    conv_stage = data["converted_stage"]
    org = data["org"]

    today = date.today()
    now_utc = datetime.combine(today, time(12, 0)).replace(tzinfo=timezone.utc)

    # Agent1: 4 calls, 2 conversions (50% rate)
    logs_agent1 = [
        AuditLog(
            organization_id=org.id, actor_user_id=agent1.id, action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead", resource_id=str(uuid.uuid4()),
            action_metadata={"status": "Picked", "new_stage_id": str(conv_stage.id)}, created_at=now_utc
        ) for _ in range(2)
    ] + [
        AuditLog(
            organization_id=org.id, actor_user_id=agent1.id, action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead", resource_id=str(uuid.uuid4()),
            action_metadata={"status": "Busy"}, created_at=now_utc
        ) for _ in range(2)
    ]

    # Agent2: 3 calls, 3 conversions (100% rate) - Top Performer
    logs_agent2 = [
        AuditLog(
            organization_id=org.id, actor_user_id=agent2.id, action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead", resource_id=str(uuid.uuid4()),
            action_metadata={"status": "Picked", "new_stage_id": str(conv_stage.id)}, created_at=now_utc
        ) for _ in range(3)
    ]

    # Agent3: 2 calls, 0 conversions (0% rate) - Low Performer
    logs_agent3 = [
        AuditLog(
            organization_id=org.id, actor_user_id=agent3.id, action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead", resource_id=str(uuid.uuid4()),
            action_metadata={"status": "Busy"}, created_at=now_utc
        ) for _ in range(2)
    ]

    db.add_all(logs_agent1 + logs_agent2 + logs_agent3)
    await db.commit()

    tl_metrics = await AnalyticsService.get_team_leader_metrics(db, tl, today)
    assert tl_metrics.total_calls_made == 9
    assert tl_metrics.total_conversions == 5
    assert len(tl_metrics.downlines) == 3

    assert tl_metrics.top_performer is not None
    assert tl_metrics.top_performer.user_id == agent2.id
    assert tl_metrics.top_performer.conversion_rate == 100.0

    assert tl_metrics.low_performer is not None
    assert tl_metrics.low_performer.user_id == agent3.id
    assert tl_metrics.low_performer.conversion_rate == 0.0

@pytest.mark.asyncio
async def test_manager_metrics_scoping(db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    manager = data["manager"]
    tl = data["tl"]
    agent1 = data["agent1"]
    org = data["org"]

    today = date.today()
    now_utc = datetime.combine(today, time(12, 0)).replace(tzinfo=timezone.utc)

    # Seed call for agent1 (reports to tl, who reports to manager)
    log = AuditLog(
        organization_id=org.id,
        actor_user_id=agent1.id,
        action="LEAD_DISPOSITION_SUBMITTED",
        resource_type="Lead",
        resource_id=str(uuid.uuid4()),
        action_metadata={"status": "Busy"},
        created_at=now_utc
    )
    db.add(log)
    await db.commit()

    mgr_metrics = await AnalyticsService.get_manager_metrics(db, manager, today)
    assert mgr_metrics.total_calls_made == 1
    assert len(mgr_metrics.teams) == 1
    assert mgr_metrics.teams[0].tl_id == tl.id
    assert mgr_metrics.teams[0].total_calls_made == 1

@pytest.mark.asyncio
async def test_super_admin_rollups_and_targets(db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    org = data["org"]
    agent1 = data["agent1"]

    today = date.today()
    now_utc = datetime.combine(today, time(12, 0)).replace(tzinfo=timezone.utc)

    # Create target: 10 calls today
    target = PerformanceTarget(
        organization_id=org.id,
        target_type=TargetType.DAILY,
        metric_type=MetricType.CALLS_MADE,
        target_value=10,
        start_date=today,
        end_date=today
    )
    db.add(target)

    # Seed 4 calls today
    logs = [
        AuditLog(
            organization_id=org.id,
            actor_user_id=agent1.id,
            action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead",
            resource_id=str(uuid.uuid4()),
            action_metadata={"status": "Busy"},
            created_at=now_utc
        ) for _ in range(4)
    ]
    db.add_all(logs)
    await db.commit()

    admin_metrics = await AnalyticsService.get_super_admin_metrics(db, org.id, today)
    assert len(admin_metrics.targets_progress) == 1
    progress = admin_metrics.targets_progress[0]
    assert progress.target_id == target.id
    assert progress.actual_value == 4
    assert progress.progress_percentage == 40.0

@pytest.mark.asyncio
async def test_analytics_api_endpoints(client: AsyncClient, setup_analytics_data):
    data = setup_analytics_data

    # Test Telecaller Guard / Route
    res_agent = await client.get("/api/v1/analytics/telecaller", headers=data["headers_agent1"])
    assert res_agent.status_code == status.HTTP_200_OK
    assert res_agent.json()["calls_made"] == 0

    res_agent_forbidden = await client.get("/api/v1/analytics/telecaller", headers=data["headers_tl"])
    assert res_agent_forbidden.status_code == status.HTTP_403_FORBIDDEN

    # Test Team Leader Guard / Route
    res_tl = await client.get("/api/v1/analytics/team-leader", headers=data["headers_tl"])
    assert res_tl.status_code == status.HTTP_200_OK
    assert res_tl.json()["total_calls_made"] == 0

    # Test Manager Guard / Route
    res_mgr = await client.get("/api/v1/analytics/manager", headers=data["headers_manager"])
    assert res_mgr.status_code == status.HTTP_200_OK
    assert res_mgr.json()["total_calls_made"] == 0

    # Test Admin / Target management routes
    # Create target
    target_payload = {
        "target_type": "DAILY",
        "metric_type": "CALLS_MADE",
        "target_value": 50,
        "start_date": str(date.today()),
        "end_date": str(date.today())
    }
    res_create = await client.post("/api/v1/analytics/targets", json=target_payload, headers=data["headers_super"])
    assert res_create.status_code == status.HTTP_201_CREATED
    assert res_create.json()["target_value"] == 50

    # List targets
    res_list = await client.get("/api/v1/analytics/targets", headers=data["headers_super"])
    assert res_list.status_code == status.HTTP_200_OK
    assert len(res_list.json()) == 1

    # Super admin metrics rollup route
    res_rollup = await client.get("/api/v1/analytics/super-admin", headers=data["headers_super"])
    assert res_rollup.status_code == status.HTTP_200_OK
    assert len(res_rollup.json()["targets_progress"]) == 1
    assert res_rollup.json()["targets_progress"][0]["target_value"] == 50


@pytest.mark.asyncio
async def test_unified_dashboard_route(client: AsyncClient, setup_analytics_data):
    data = setup_analytics_data
    
    # 1. Telecaller dashboard
    res_agent = await client.get("/api/v1/analytics/dashboard", headers=data["headers_agent1"])
    assert res_agent.status_code == status.HTTP_200_OK
    assert res_agent.json()["role"] == "Telecaller"
    assert "calls_made" in res_agent.json()["metrics"]
    
    # 2. Team Leader dashboard
    res_tl = await client.get("/api/v1/analytics/dashboard", headers=data["headers_tl"])
    assert res_tl.status_code == status.HTTP_200_OK
    assert res_tl.json()["role"] == "TeamLeader"
    assert "total_calls_made" in res_tl.json()["metrics"]
    assert "downlines" in res_tl.json()["metrics"]

    # 3. Manager dashboard
    res_mgr = await client.get("/api/v1/analytics/dashboard", headers=data["headers_manager"])
    assert res_mgr.status_code == status.HTTP_200_OK
    assert res_mgr.json()["role"] == "Manager"
    assert "teams" in res_mgr.json()["metrics"]

    # 4. SuperAdmin dashboard
    res_super = await client.get("/api/v1/analytics/dashboard", headers=data["headers_super"])
    assert res_super.status_code == status.HTTP_200_OK
    assert res_super.json()["role"] == "SuperAdmin"
    assert "targets_progress" in res_super.json()["metrics"]


@pytest.mark.asyncio
async def test_leads_name_city_search_route(client: AsyncClient, db: AsyncSession, setup_analytics_data):
    data = setup_analytics_data
    org = data["org"]
    admin = data["super_admin"]
    conv_stage = data["converted_stage"]

    # Create leads with name/city
    from app.models.lead import Lead
    lead1 = Lead(
        organization_id=org.id,
        first_name="Johnny",
        last_name="Depp",
        title="Actor",
        status="New",
        city="Boston",
        created_by=admin.id,
        stage_id=conv_stage.id
    )
    lead2 = Lead(
        organization_id=org.id,
        first_name="Alice",
        last_name="Smith",
        title="CEO",
        status="New",
        city="Chicago",
        created_by=admin.id,
        stage_id=conv_stage.id
    )
    lead3 = Lead(
        organization_id=org.id,
        first_name="Bob",
        last_name="Johnson",
        title="Developer",
        status="New",
        city="Houston",
        created_by=admin.id,
        stage_id=conv_stage.id
    )
    db.add_all([lead1, lead2, lead3])
    await db.commit()

    # 1. Search by name "john" -> should match Johnny and Johnson (lead1, lead3)
    res_name = await client.get("/api/v1/leads/?name=john", headers=data["headers_super"])
    assert res_name.status_code == status.HTTP_200_OK
    items = res_name.json()
    assert len(items) == 2
    names = {item["first_name"] or item["last_name"] for item in items}
    assert "Johnny" in names
    assert "Bob" in names # last_name is Johnson

    # 2. Search by city "boston" -> should match Johnny (lead1)
    res_city = await client.get("/api/v1/leads/?city=boston", headers=data["headers_super"])
    assert res_city.status_code == status.HTTP_200_OK
    items_city = res_city.json()
    assert len(items_city) == 1
    assert items_city[0]["first_name"] == "Johnny"
    assert items_city[0]["city"] == "Boston"

    # 3. Search by general search query "houston" -> should match Bob (lead3)
    res_search = await client.get("/api/v1/leads/?search=houston", headers=data["headers_super"])
    assert res_search.status_code == status.HTTP_200_OK
    items_search = res_search.json()
    assert len(items_search) == 1
    assert items_search[0]["first_name"] == "Bob"

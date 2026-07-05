import pytest
import uuid
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.pipeline import PipelineStage
from app.models.notification import Notification
from app.models.performance import PerformanceAchievement
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key): return storage.get(key)
    async def mock_set(key, value, ex=300): storage[key] = value; return True
    async def mock_delete(key): storage.pop(key, None); return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_features(*a, **k):
        return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Perf Org", "slug": "perf-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@pf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@pf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@pf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    emp2 = await user_repo.create_user(org.id, {
        "email": "emp2@pf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Three", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp, "emp2": emp2, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _seed_perf(db, org, user, *, won=0, value=1000, calls=0, when=None, stage=None):
    when = when or datetime.now(timezone.utc)
    stage_id = stage.id if stage is not None else (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id).limit(1))).scalar()
    for i in range(won):
        db.add(Lead(organization_id=org.id, last_name=f"W{i}", title=f"W{i}", status="Won", value=value,
                    created_by=user.id, assigned_user_id=user.id, created_at=when, stage_id=stage_id))
    for i in range(calls):
        db.add(Activity(organization_id=org.id, activity_type="Call", subject=f"Call {i}",
                        assigned_user_id=user.id, created_by=user.id, created_at=when))
    await db.commit()


@pytest.mark.asyncio
async def test_kpi_crud_seed_and_permissions(client: AsyncClient, setup: dict):
    data = setup
    # employee cannot create KPIs
    assert (await client.post("/api/v1/performance/kpis", json={
        "name": "X", "metric": "calls_made"}, headers=data["h_emp"])).status_code == 403
    # invalid metric rejected
    assert (await client.post("/api/v1/performance/kpis", json={
        "name": "X", "metric": "vibes"}, headers=data["h_admin"])).status_code == 400
    k = (await client.post("/api/v1/performance/kpis", json={
        "name": "Sales", "code": "SALES", "metric": "sales_revenue", "weight": 3}, headers=data["h_admin"])).json()
    assert k["unit"] == "currency" and k["weight"] == 3.0
    # seed defaults (skips the existing SALES code)
    r = await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["created"] == 6
    # employee can view active KPIs
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_emp"])).json()
    assert any(x["metric"] == "attendance_score" for x in kpis)


@pytest.mark.asyncio
async def test_scorecard_metrics_and_composite(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _seed_perf(db, data["org"], data["emp"], won=2, value=5000, calls=10)
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    # set a sales goal so attainment + composite compute
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    sales_kpi = next(k for k in kpis if k["metric"] == "sales_revenue")
    today = date.today()
    await client.post("/api/v1/performance/goals", json={
        "user_id": str(data["emp"].id), "kpi_id": sales_kpi["id"], "period": "monthly",
        "target_value": 20000, "start_date": today.replace(day=1).isoformat(), "end_date": today.isoformat()},
        headers=data["h_mgr"])
    sc = (await client.get("/api/v1/performance/scorecard", params={"user_id": str(data["emp"].id)},
                           headers=data["h_mgr"])).json()
    assert sc["metrics"]["sales_revenue"] == 10000.0 and sc["metrics"]["leads_converted"] == 2
    assert sc["metrics"]["calls_made"] == 10 and sc["metrics"]["conversion_rate"] == 100.0
    row = next(r for r in sc["kpis"] if r["metric"] == "sales_revenue")
    assert row["target"] == 20000.0 and row["attainment"] == 50.0
    assert sc["composite_score"] is not None
    # employee can view own scorecard, not the manager's
    assert (await client.get("/api/v1/performance/scorecard", headers=data["h_emp"])).status_code == 200
    assert (await client.get("/api/v1/performance/scorecard", params={"user_id": str(data["mgr"].id)},
                             headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_goal_permissions_and_attainment(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    today = date.today()
    # employee cannot set goals
    assert (await client.post("/api/v1/performance/goals", json={
        "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"], "target_value": 5,
        "start_date": today.replace(day=1).isoformat(), "end_date": today.isoformat()}, headers=data["h_emp"])).status_code == 403
    # manager sets a goal for the employee → employee notified
    r = await client.post("/api/v1/performance/goals", json={
        "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"], "period": "monthly", "target_value": 4,
        "start_date": today.replace(day=1).isoformat(), "end_date": today.isoformat()}, headers=data["h_mgr"])
    assert r.status_code == 201
    goal = r.json()
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.title == "New performance goal"))).scalars().first()
    assert notif is not None
    # seed 2 conversions → attainment 50%
    await _seed_perf(db, data["org"], data["emp"], won=2)
    goals = (await client.get("/api/v1/performance/goals", params={"user_id": str(data["emp"].id)}, headers=data["h_mgr"])).json()
    g = next(x for x in goals if x["id"] == goal["id"])
    assert g["actual"] == 2.0 and g["attainment"] == 50.0


@pytest.mark.asyncio
async def test_leaderboard_ranks_users(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _seed_perf(db, data["org"], data["emp"], won=1, value=9000)
    await _seed_perf(db, data["org"], data["emp2"], won=1, value=3000)
    board = (await client.get("/api/v1/performance/leaderboard", params={"metric": "sales_revenue"}, headers=data["h_admin"])).json()
    ranked = [(r["rank"], r["value"]) for r in board]
    assert ranked[0][0] == 1 and ranked[0][1] == 9000.0
    top_ids = [r["user_id"] for r in board]
    assert top_ids[0] == str(data["emp"].id)
    # invalid metric rejected
    assert (await client.get("/api/v1/performance/leaderboard", params={"metric": "nope"}, headers=data["h_admin"])).status_code == 400


@pytest.mark.asyncio
async def test_achievements_evaluate_notify_and_idempotent(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    today = date.today()
    await client.post("/api/v1/performance/goals", json={
        "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"], "period": "monthly", "target_value": 2,
        "start_date": today.replace(day=1).isoformat(), "end_date": today.isoformat()}, headers=data["h_mgr"])
    # 3 conversions vs target 2 → 150% → Gold
    await _seed_perf(db, data["org"], data["emp"], won=3)
    r = await client.post("/api/v1/performance/achievements/evaluate", json={}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["awarded"] == 1
    ach = (await client.get("/api/v1/performance/achievements", params={"user_id": str(data["emp"].id)}, headers=data["h_mgr"])).json()
    assert ach[0]["badge"] == "Gold" and ach[0]["attainment"] == 150.0
    # employee notified of the achievement
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.title.like("Achievement unlocked%")))).scalars().first() is not None
    # re-evaluating does not duplicate
    assert (await client.post("/api/v1/performance/achievements/evaluate", json={}, headers=data["h_mgr"])).json()["awarded"] == 0
    total = (await db.execute(select(PerformanceAchievement).filter(
        PerformanceAchievement.user_id == data["emp"].id))).scalars().all()
    assert len(total) == 1
    # employees cannot evaluate
    assert (await client.post("/api/v1/performance/achievements/evaluate", json={}, headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_trend_dashboard_and_report(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _seed_perf(db, data["org"], data["emp"], won=1, value=4000, calls=3)
    # trend (weekly buckets)
    tr = (await client.get("/api/v1/performance/trend", params={
        "user_id": str(data["emp"].id), "granularity": "weekly", "count": 4}, headers=data["h_mgr"])).json()
    assert tr["granularity"] == "weekly" and len(tr["series"]) == 4
    # dashboard for the employee
    dash = (await client.get("/api/v1/performance/dashboard", headers=data["h_emp"])).json()
    assert "my_metrics" in dash and "my_composite_score" in dash
    # report (manager sees team)
    rep = (await client.get("/api/v1/performance/report", headers=data["h_mgr"])).json()
    row = next(r for r in rep["rows"] if r["user_id"] == str(data["emp"].id))
    assert row["sales_revenue"] == 4000.0 and row["calls_made"] == 3


@pytest.mark.asyncio
async def test_workflow_goal_achieved(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    today = date.today()
    # rule: on goal_achieved → notify the manager
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Goal hit", "trigger_event": "goal_achieved", "conditions": [],
        "actions": [{"type": "notify_manager", "message": "Target reached"}]}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text
    await client.post("/api/v1/performance/goals", json={
        "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"], "period": "monthly", "target_value": 1,
        "start_date": today.replace(day=1).isoformat(), "end_date": today.isoformat()}, headers=data["h_mgr"])
    await _seed_perf(db, data["org"], data["emp"], won=2)
    await client.post("/api/v1/performance/achievements/evaluate", json={}, headers=data["h_mgr"])
    # workflow fired → manager (of emp) notified
    wf = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "performance",
        Notification.title == "Workflow: Goal hit"))).scalars().first()
    assert wf is not None
    # invalid action for performance entity rejected
    bad = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad", "trigger_event": "goal_achieved", "conditions": [],
        "actions": [{"type": "set_status", "value": "x"}]}, headers=data["h_admin"])
    assert bad.status_code == 400

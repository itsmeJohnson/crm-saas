import pytest
import uuid
from datetime import date, datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.team import Team, TeamMember, TeamTarget
from app.models.department import Department, DepartmentTarget
from app.models.performance import PerformanceGoal
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
        return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Tgt Org", "slug": "tgt-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@tg.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@tg.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@tg.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _won(db, org, user, n, value, stage):
    for i in range(n):
        db.add(Lead(organization_id=org.id, last_name=f"W{i}", title=f"W{i}", status="Won", value=value,
                    created_by=user.id, assigned_user_id=user.id, stage_id=stage.id))
    await db.commit()


@pytest.mark.asyncio
async def test_delegating_create_across_scopes_and_unified_list(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    today = date.today()
    m0, m1 = today.replace(day=1).isoformat(), today.isoformat()
    # seed a KPI for the individual scope
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    # a team + a department
    team = (await client.post("/api/v1/teams", json={"name": "Alpha", "team_leader_id": str(data["mgr"].id)}, headers=data["h_admin"])).json()
    await client.post(f"/api/v1/teams/{team['id']}/members", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    dept = (await client.post("/api/v1/departments", json={"name": "Sales"}, headers=data["h_admin"])).json()
    await client.post(f"/api/v1/departments/{dept['id']}/members", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])

    # create one target of each scope through the unified endpoint (delegates)
    r = await client.post("/api/v1/targets", json={
        "scope": "individual", "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"],
        "period": "monthly", "target_value": 4, "start_date": m0, "end_date": m1}, headers=data["h_mgr"])
    assert r.status_code == 201, r.text
    assert (await client.post("/api/v1/targets", json={
        "scope": "team", "team_id": team["id"], "name": "Team conv", "metric": "leads_converted",
        "period": "monthly", "target_value": 6}, headers=data["h_admin"])).status_code == 201
    assert (await client.post("/api/v1/targets", json={
        "scope": "department", "department_id": dept["id"], "name": "Dept conv", "metric": "leads_converted",
        "period": "quarterly", "target_value": 10}, headers=data["h_admin"])).status_code == 201
    # underlying stores got the rows
    assert len((await db.execute(select(PerformanceGoal))).scalars().all()) == 1
    assert len((await db.execute(select(TeamTarget))).scalars().all()) == 1
    assert len((await db.execute(select(DepartmentTarget))).scalars().all()) == 1

    # unified list shows all three scopes
    rows = (await client.get("/api/v1/targets", headers=data["h_admin"])).json()
    scopes = {r["scope"] for r in rows}
    assert scopes == {"individual", "team", "department"}
    # scope filter
    team_rows = (await client.get("/api/v1/targets", params={"scope": "team"}, headers=data["h_admin"])).json()
    assert all(r["scope"] == "team" for r in team_rows) and len(team_rows) == 1
    # period filter
    q_rows = (await client.get("/api/v1/targets", params={"period": "quarterly"}, headers=data["h_admin"])).json()
    assert len(q_rows) == 1 and q_rows[0]["scope"] == "department"


@pytest.mark.asyncio
async def test_progress_and_achievement_computed(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    today = date.today()
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    await client.post("/api/v1/targets", json={
        "scope": "individual", "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"],
        "period": "monthly", "target_value": 2, "start_date": today.replace(day=1).isoformat(),
        "end_date": today.isoformat()}, headers=data["h_mgr"])
    # 3 conversions vs target 2 → achieved, attainment 150
    await _won(db, data["org"], data["emp"], 3, 1000, data["stage"])
    rows = (await client.get("/api/v1/targets", params={"scope": "individual"}, headers=data["h_admin"])).json()
    row = rows[0]
    assert row["actual"] == 3.0 and row["attainment"] == 150.0
    assert row["achieved"] is True and row["status_label"] == "achieved"


@pytest.mark.asyncio
async def test_dashboard_report_and_scope_visibility(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    today = date.today()
    await client.post("/api/v1/performance/kpis/seed", json={}, headers=data["h_admin"])
    kpis = (await client.get("/api/v1/performance/kpis", headers=data["h_admin"])).json()
    conv_kpi = next(k for k in kpis if k["metric"] == "leads_converted")
    # a goal for the employee (at risk — target high, no data)
    await client.post("/api/v1/targets", json={
        "scope": "individual", "user_id": str(data["emp"].id), "kpi_id": conv_kpi["id"],
        "period": "monthly", "target_value": 100, "start_date": today.replace(day=1).isoformat(),
        "end_date": today.isoformat()}, headers=data["h_mgr"])

    dash = (await client.get("/api/v1/targets/dashboard", headers=data["h_admin"])).json()
    assert dash["total"] >= 1 and "by_scope" in dash and "avg_attainment" in dash

    rep = (await client.get("/api/v1/targets/report", headers=data["h_admin"])).json()
    assert rep["count"] == len(rep["rows"]) and rep["count"] >= 1

    # employee sees only their own individual target (scope visibility)
    emp_rows = (await client.get("/api/v1/targets", headers=data["h_emp"])).json()
    assert all(r["scope_name"] == "Emp Two" for r in emp_rows if r["scope"] == "individual")

    # invalid scope on create rejected
    assert (await client.post("/api/v1/targets", json={
        "scope": "galaxy", "target_value": 5}, headers=data["h_admin"])).status_code == 422
    # individual create without kpi_id rejected
    assert (await client.post("/api/v1/targets", json={
        "scope": "individual", "user_id": str(data["emp"].id), "target_value": 5,
        "period": "monthly"}, headers=data["h_mgr"])).status_code == 400

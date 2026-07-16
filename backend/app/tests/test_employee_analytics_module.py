import pytest
import uuid
from datetime import datetime, date, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.task import Task
from app.models.activity import Activity
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.models.employee_training import EmployeeTraining
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    store = {}
    async def g(k): return store.get(k)
    async def s(k, v, ex=300): store[k] = v; return True
    async def d(k): store.pop(k, None); return True
    monkeypatch.setattr(redis_client, "get", g)
    monkeypatch.setattr(redis_client, "set", s)
    monkeypatch.setattr(redis_client, "delete", d)
    from app.dependencies import feature_guard
    async def feats(*a, **k): return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Emp Org", "slug": "emp-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@ea.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await ur.create_user(org.id, {"email": "mgr@ea.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Man", "last_name": "Ager", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    e1 = await ur.create_user(org.id, {"email": "e1@ea.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "One", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
    e2 = await ur.create_user(org.id, {"email": "e2@ea.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
    outsider = await ur.create_user(org.id, {"email": "out@ea.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Out", "last_name": "Sider", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    today = date.today()

    # e1: 2 leads (1 converted), 3 calls, 2 tasks (1 done), present 4 days, 1 training score 90
    db.add(Lead(organization_id=org.id, last_name="L", title="t", status="Converted", value=1000,
                converted_at=now, assigned_user_id=e1.id, created_by=admin.id, stage_id=stage.id))
    db.add(Lead(organization_id=org.id, last_name="L", title="t", status="New", value=500,
                assigned_user_id=e1.id, created_by=admin.id, stage_id=stage.id))
    for i in range(3):
        db.add(Activity(organization_id=org.id, activity_type="Call", subject="c", status="Completed",
                        assigned_user_id=e1.id, created_by=e1.id, call_direction="OUTBOUND"))
    db.add(Task(organization_id=org.id, title="t1", status="Done", assigned_user_id=e1.id, created_by=e1.id))
    db.add(Task(organization_id=org.id, title="t2", status="Todo", assigned_user_id=e1.id, created_by=e1.id))
    for i in range(4):
        db.add(AttendanceRecord(organization_id=org.id, user_id=e1.id, work_date=today - timedelta(days=i), status="present"))
    db.add(AttendanceRecord(organization_id=org.id, user_id=e1.id, work_date=today - timedelta(days=5), status="absent"))
    db.add(EmployeeTraining(organization_id=org.id, user_id=e1.id, name="Sales 101", status="completed", score=90,
                            completed_at=now, created_by=admin.id))
    # e2: fewer, plus an approved leave
    db.add(Task(organization_id=org.id, title="t3", status="Done", assigned_user_id=e2.id, created_by=e2.id))
    db.add(AttendanceRecord(organization_id=org.id, user_id=e2.id, work_date=today, status="present"))
    db.add(LeaveRequest(organization_id=org.id, user_id=e2.id, request_type="leave",
                        start_date=today - timedelta(days=2), end_date=today - timedelta(days=1), day_count=2,
                        status="approved", created_by=e2.id))
    await db.commit()
    return {"org": org, "admin": admin, "mgr": mgr, "e1": e1, "e2": e2, "outsider": outsider, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
            "h_e1": {"Authorization": f"Bearer {create_access_token(e1.id)}"}}


@pytest.mark.asyncio
async def test_roster_productivity_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    # employees cannot open employee analytics
    assert (await client.get("/api/v1/employee-analytics/roster", headers=d["h_e1"])).status_code == 403
    r = (await client.get("/api/v1/employee-analytics/roster", headers=d["h_admin"])).json()
    assert r["headcount"] >= 4
    e1row = next(x for x in r["employees"] if x["user_id"] == str(d["e1"].id))
    assert e1row["leads_converted"] == 1 and e1row["calls"] == 3
    assert e1row["tasks_total"] == 2 and e1row["tasks_done"] == 1 and e1row["task_completion_rate"] == 50.0
    assert e1row["attendance_rate"] == 80.0  # 4 present of 5 (4 present + 1 absent)
    assert e1row["training_score"] == 90.0 and e1row["productivity_score"] > 0
    # roster is sorted by productivity desc
    scores = [x["productivity_score"] for x in r["employees"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_manager_scope_and_employee_deepdive(client: AsyncClient, setup: dict):
    d = setup
    # manager sees only downline (e1, e2, self) — not the admin's outsider
    r = (await client.get("/api/v1/employee-analytics/roster", headers=d["h_mgr"])).json()
    ids = {x["user_id"] for x in r["employees"]}
    assert str(d["e1"].id) in ids and str(d["outsider"].id) not in ids
    # manager cannot deep-dive the outsider
    assert (await client.get(f"/api/v1/employee-analytics/{d['outsider'].id}", headers=d["h_mgr"])).status_code == 403
    emp = (await client.get(f"/api/v1/employee-analytics/{d['e1'].id}", headers=d["h_mgr"])).json()
    assert emp["lead_productivity"]["leads_converted"] == 1
    assert emp["task_completion"]["completion_rate"] == 50.0
    assert emp["attendance"]["attendance_rate"] == 80.0
    assert emp["training"]["avg_score"] == 90.0 and emp["training"]["count"] == 1


@pytest.mark.asyncio
async def test_comparisons_leaderboard_and_trends(client: AsyncClient, setup: dict):
    d = setup
    mc = (await client.get("/api/v1/employee-analytics/manager-comparison", headers=d["h_admin"])).json()
    mgr_row = next((m for m in mc["managers"] if m["manager_id"] == str(d["mgr"].id)), None)
    assert mgr_row is not None and mgr_row["team_size"] == 2 and mgr_row["leads_converted"] == 1
    dep = (await client.get("/api/v1/employee-analytics/comparison/department", headers=d["h_admin"])).json()
    assert dep["kind"] == "department" and "rows" in dep
    assert (await client.get("/api/v1/employee-analytics/comparison/bogus", headers=d["h_admin"])).status_code == 400
    lb = (await client.get("/api/v1/employee-analytics/leaderboard", params={"metric": "leads_converted"}, headers=d["h_admin"])).json()
    assert any(x.get("user_id") == str(d["e1"].id) for x in lb)
    at = (await client.get("/api/v1/employee-analytics/attendance-trend", headers=d["h_admin"])).json()
    assert "series" in at and sum(b["present"] for b in at["series"]) >= 5
    pt = (await client.get(f"/api/v1/employee-analytics/{d['e1'].id}/performance-trend", params={"granularity": "weekly", "count": 4}, headers=d["h_admin"])).json()
    assert pt["granularity"] == "weekly" and len(pt["series"]) == 4


@pytest.mark.asyncio
async def test_heatmap_dashboard_export_and_training_crud(client: AsyncClient, setup: dict):
    d = setup
    hm = (await client.get("/api/v1/employee-analytics/heatmap", headers=d["h_admin"])).json()
    assert len(hm["grid"]) == 7 and len(hm["grid"][0]) == 24 and hm["total"] >= 3
    dash = (await client.get("/api/v1/employee-analytics/dashboard", headers=d["h_admin"])).json()
    assert dash["headcount"] >= 4 and "avg_productivity" in dash and dash["top_performer"] is not None
    exp = await client.get("/api/v1/employee-analytics/export", headers=d["h_admin"])
    assert exp.status_code == 200 and "Employee analytics" in exp.text and "Training" in exp.text
    # training CRUD
    assert (await client.post("/api/v1/employee-analytics/trainings",
            json={"user_id": str(d["e2"].id), "name": "x", "score": 70}, headers=d["h_e1"])).status_code == 403
    t = (await client.post("/api/v1/employee-analytics/trainings", json={
        "user_id": str(d["e2"].id), "name": "Onboarding", "status": "completed", "score": 75}, headers=d["h_admin"])).json()
    assert t["score"] == 75
    # invalid score rejected
    assert (await client.post("/api/v1/employee-analytics/trainings",
            json={"user_id": str(d["e2"].id), "name": "bad", "score": 200}, headers=d["h_admin"])).status_code == 422
    upd = (await client.patch(f"/api/v1/employee-analytics/trainings/{t['id']}", json={"score": 88}, headers=d["h_admin"])).json()
    assert upd["score"] == 88
    # now e2's training score shows in roster
    r = (await client.get("/api/v1/employee-analytics/roster", headers=d["h_admin"])).json()
    e2row = next(x for x in r["employees"] if x["user_id"] == str(d["e2"].id))
    assert e2row["training_score"] == 88.0
    assert (await client.delete(f"/api/v1/employee-analytics/trainings/{t['id']}", headers=d["h_admin"])).status_code == 204

import pytest
import uuid
from datetime import datetime, timezone, timedelta
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
from app.models.calendar_event import CalendarEvent
from app.models.pipeline import PipelineStage
from app.models.announcement import Announcement
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
    org = await org_repo.create({"name": "Emp Dash Org", "slug": "emp-dash-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@ed.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@ed.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@ed.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
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


@pytest.mark.asyncio
async def test_employee_summary_scoped_to_self(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    now = datetime.now(timezone.utc)
    # leads: 2 for emp (1 Won), 1 for mgr — emp summary must only count emp's
    db.add(Lead(organization_id=data["org"].id, last_name="A", title="A", status="Won", value=100,
                created_by=data["emp"].id, assigned_user_id=data["emp"].id, stage_id=data["stage"].id))
    db.add(Lead(organization_id=data["org"].id, last_name="B", title="B", status="New",
                created_by=data["emp"].id, assigned_user_id=data["emp"].id, stage_id=data["stage"].id))
    db.add(Lead(organization_id=data["org"].id, last_name="C", title="C", status="New",
                created_by=data["mgr"].id, assigned_user_id=data["mgr"].id, stage_id=data["stage"].id))
    # today's calls: 2 for emp
    for i in range(2):
        db.add(Activity(organization_id=data["org"].id, activity_type="Call", subject=f"Call {i}",
                        assigned_user_id=data["emp"].id, created_by=data["emp"].id, created_at=now))
    # a meeting today for emp
    db.add(CalendarEvent(organization_id=data["org"].id, title="Standup", event_type="Meeting",
                         start_at=now + timedelta(hours=1), end_at=now + timedelta(hours=2),
                         assigned_user_id=data["emp"].id, created_by=data["emp"].id))
    # tasks: 1 open + 1 overdue for emp
    db.add(Task(organization_id=data["org"].id, title="T1", status="Todo",
                created_by=data["emp"].id, assigned_user_id=data["emp"].id))
    db.add(Task(organization_id=data["org"].id, title="T2", status="InProgress",
                due_date=now - timedelta(days=1), created_by=data["emp"].id, assigned_user_id=data["emp"].id))
    await db.commit()

    s = (await client.get("/api/v1/dashboard/employee", headers=data["h_emp"])).json()
    assert s["my_leads_total"] == 2 and s["my_leads_converted"] == 1
    assert s["today_calls"] == 2
    assert s["today_meetings_count"] == 1 and s["today_meetings"][0]["title"] == "Standup"
    assert s["open_tasks"] == 2 and s["overdue_tasks"] == 1

    # Employee hero card fields (Phase 4) — present and self-scoped
    for f in ("employee_name", "is_online", "check_in_at", "working_minutes", "calls_made_today",
              "todays_follow_ups", "overdue_follow_ups", "new_leads", "interested_leads",
              "meetings_today", "tasks_pending"):
        assert f in s, f"missing hero field {f}"
    assert s["calls_made_today"] == s["today_calls"]
    assert s["meetings_today"] == s["today_meetings_count"]
    assert s["tasks_pending"] == s["open_tasks"]
    assert s["is_online"] is False and s["working_minutes"] == 0  # no attendance clock-in in this fixture

    # the manager's own summary sees only the manager's 1 lead (scoped, not team)
    sm = (await client.get("/api/v1/dashboard/employee", headers=data["h_mgr"])).json()
    assert sm["my_leads_total"] == 1


@pytest.mark.asyncio
async def test_announcements_audience_and_permissions(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # employee cannot create
    assert (await client.post("/api/v1/announcements", json={"title": "x", "body": "y"}, headers=data["h_emp"])).status_code == 403
    # manager posts one to all + one to Managers only
    a1 = (await client.post("/api/v1/announcements", json={
        "title": "Town hall", "body": "Friday 4pm", "audience": "all", "is_pinned": True}, headers=data["h_mgr"])).json()
    assert a1["is_pinned"] is True and a1["author_name"] == "Mgr One"
    await client.post("/api/v1/announcements", json={
        "title": "Mgr sync", "body": "internal", "audience": "Manager"}, headers=data["h_admin"])
    # invalid audience rejected by the schema pattern
    assert (await client.post("/api/v1/announcements", json={
        "title": "z", "body": "z", "audience": "aliens"}, headers=data["h_mgr"])).status_code == 422

    # employee sees only the 'all' announcement (pinned first), not the Manager-only one
    emp_list = (await client.get("/api/v1/announcements", headers=data["h_emp"])).json()
    titles = [a["title"] for a in emp_list]
    assert "Town hall" in titles and "Mgr sync" not in titles
    # manager sees both via their audience + all
    mgr_list = (await client.get("/api/v1/announcements", headers=data["h_mgr"])).json()
    assert {"Town hall", "Mgr sync"}.issubset({a["title"] for a in mgr_list})
    # manager management view (scope=all) lists everything incl inactive
    all_list = (await client.get("/api/v1/announcements", params={"scope": "all"}, headers=data["h_admin"])).json()
    assert len(all_list) == 2

    # expired announcements are hidden from the employee feed
    exp = Announcement(organization_id=data["org"].id, title="Old", body="past", audience="all",
                       published_at=datetime.now(timezone.utc) - timedelta(days=5),
                       expires_at=datetime.now(timezone.utc) - timedelta(days=1), created_by=data["mgr"].id)
    db.add(exp); await db.commit()
    emp_list2 = (await client.get("/api/v1/announcements", headers=data["h_emp"])).json()
    assert "Old" not in [a["title"] for a in emp_list2]

    # delete
    await client.delete(f"/api/v1/announcements/{a1['id']}", headers=data["h_mgr"])
    assert "Town hall" not in [a["title"] for a in (await client.get("/api/v1/announcements", headers=data["h_emp"])).json()]

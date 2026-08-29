import pytest
import uuid
from datetime import datetime, timezone, timedelta, date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.scheduler import Schedule, ScheduleRun
from app.models.calendar_event import Holiday, WorkingHoursConfig
from app.services import cron_utils
from app.services.scheduler_service import SchedulerService
from app.core.redis import redis_client


# ---------------- pure cron parser unit tests (no DB) ----------------
def test_cron_validation_and_matching():
    assert cron_utils.is_valid_cron("0 9 * * 1-5")
    assert cron_utils.is_valid_cron("*/15 * * * *")
    assert not cron_utils.is_valid_cron("bad")
    assert not cron_utils.is_valid_cron("60 0 * * *")   # minute out of range
    assert not cron_utils.is_valid_cron("0 0 * *")      # too few fields
    # a Monday 09:00
    assert cron_utils.cron_matches("0 9 * * 1", datetime(2026, 7, 6, 9, 0))    # Mon
    assert not cron_utils.cron_matches("0 9 * * 1", datetime(2026, 7, 7, 9, 0))  # Tue


def test_cron_next_variants():
    # every 15 minutes
    assert cron_utils.cron_next("*/15 * * * *", datetime(2026, 7, 6, 10, 7)) == datetime(2026, 7, 6, 10, 15)
    # weekly Monday 09:00, from a Saturday
    assert cron_utils.cron_next("0 9 * * 1", datetime(2026, 7, 4, 12, 0)) == datetime(2026, 7, 6, 9, 0)
    # monthly on the 15th at 09:00
    assert cron_utils.cron_next("0 9 15 * *", datetime(2026, 7, 6, 0, 0)) == datetime(2026, 7, 15, 9, 0)
    # business-hours range 09:00 weekdays — next after Fri 18:00 is Mon 09:00
    assert cron_utils.cron_next("0 9 * * 1-5", datetime(2026, 7, 3, 18, 0)) == datetime(2026, 7, 6, 9, 0)


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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Sch Org", "slug": "sch-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@sch.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@sch.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_crud_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/scheduler/catalog", headers=d["h_admin"])).json()
    assert "cron" in cat["schedule_kinds"] and "run_automation_job" in cat["task_types"]
    # employee cannot create
    assert (await client.post("/api/v1/scheduler", json={"name": "x", "task_type": "noop"}, headers=d["h_emp"])).status_code == 403
    # invalid cron rejected
    assert (await client.post("/api/v1/scheduler", json={"name": "x", "task_type": "noop", "schedule_kind": "cron", "cron_expr": "bad"}, headers=d["h_admin"])).status_code == 400
    # daily schedule → next_run_at computed
    s = (await client.post("/api/v1/scheduler", json={
        "name": "Nightly", "task_type": "noop", "schedule_kind": "daily", "time_of_day": "02:00"}, headers=d["h_admin"])).json()
    assert s["next_run_at"] is not None and s["schedule_kind"] == "daily"
    # preview next runs
    nxt = (await client.get(f"/api/v1/scheduler/{s['id']}/next-runs", headers=d["h_admin"])).json()
    assert len(nxt["next_runs"]) >= 1


@pytest.mark.asyncio
async def test_compute_next_run_kinds(setup: dict, db: AsyncSession):
    d = setup
    svc = SchedulerService(db)
    after = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)  # Monday
    weekly = Schedule(organization_id=d["org"].id, name="w", task_type="noop", schedule_kind="weekly",
                      day_of_week=2, time_of_day="09:00", timezone="UTC", created_by=d["admin"].id)
    nxt = svc.compute_next_run(weekly, after)
    assert nxt.weekday() == 2 and nxt.hour == 9  # Wednesday 09:00
    monthly = Schedule(organization_id=d["org"].id, name="m", task_type="noop", schedule_kind="monthly",
                       day_of_month=15, time_of_day="08:30", timezone="UTC", created_by=d["admin"].id)
    nm = svc.compute_next_run(monthly, after)
    assert nm.day == 15 and nm.hour == 8 and nm.minute == 30
    interval = Schedule(organization_id=d["org"].id, name="i", task_type="noop", schedule_kind="interval",
                        interval_minutes=30, timezone="UTC", created_by=d["admin"].id)
    assert svc.compute_next_run(interval, after) == after + timedelta(minutes=30)


@pytest.mark.asyncio
async def test_run_due_executes_records_and_advances(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # a due schedule (next_run in the past) that publishes an event
    s = Schedule(organization_id=d["org"].id, name="tick", task_type="event_publish",
                 task_config={"event_type": "custom.tick"}, schedule_kind="interval", interval_minutes=15,
                 timezone="UTC", is_active=True, next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                 created_by=d["admin"].id)
    db.add(s); await db.commit()
    fired = await SchedulerService(db).run_due(org_id=d["org"].id)
    assert fired == 1
    await db.refresh(s)
    assert s.run_count == 1 and s.last_status == "success"
    nxt = s.next_run_at if s.next_run_at.tzinfo else s.next_run_at.replace(tzinfo=timezone.utc)
    assert nxt > datetime.now(timezone.utc)  # advanced into the future
    # a run row was recorded
    runs = (await db.execute(select(ScheduleRun).filter(ScheduleRun.schedule_id == s.id))).scalars().all()
    assert len(runs) == 1 and runs[0].status == "success"


@pytest.mark.asyncio
async def test_holiday_and_business_hours_gating(setup: dict, db: AsyncSession):
    d = setup
    # configure business hours Mon-Fri 09-17 + a holiday today
    today = datetime.now(timezone.utc).date()
    db.add(WorkingHoursConfig(organization_id=d["org"].id, timezone="UTC", days={
        "mon": {"enabled": True, "start": "09:00", "end": "17:00"},
        "tue": {"enabled": True, "start": "09:00", "end": "17:00"},
        "wed": {"enabled": True, "start": "09:00", "end": "17:00"},
        "thu": {"enabled": True, "start": "09:00", "end": "17:00"},
        "fri": {"enabled": True, "start": "09:00", "end": "17:00"},
        "sat": {"enabled": False}, "sun": {"enabled": False}}))
    db.add(Holiday(organization_id=d["org"].id, name="Test Holiday", holiday_date=today,
                   recurring_annual=False, created_by=d["admin"].id))
    await db.commit()
    svc = SchedulerService(db)
    # skip_holidays schedule → run is recorded as skipped(holiday), not executed
    s = Schedule(organization_id=d["org"].id, name="holiday-aware", task_type="noop", schedule_kind="daily",
                 skip_holidays=True, is_active=True, next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                 created_by=d["admin"].id)
    db.add(s); await db.commit()
    await svc.run_due(org_id=d["org"].id)
    await db.refresh(s)
    run = (await db.execute(select(ScheduleRun).filter(ScheduleRun.schedule_id == s.id))).scalars().first()
    assert run.status == "skipped" and run.reason == "holiday" and s.skip_count == 1 and s.run_count == 0


@pytest.mark.asyncio
async def test_retry_on_failure_and_history(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # a webhook task with no url → raises → retried up to max_retries → failed
    s = (await client.post("/api/v1/scheduler", json={
        "name": "bad hook", "task_type": "webhook", "task_config": {}, "schedule_kind": "daily",
        "time_of_day": "09:00", "max_retries": 3}, headers=d["h_admin"])).json()
    run = (await client.post(f"/api/v1/scheduler/{s['id']}/run", headers=d["h_admin"])).json()
    assert run["status"] == "failed" and run["attempts"] == 3 and run["triggered_by"] == "manual"
    # execution history endpoint
    hist = (await client.get("/api/v1/scheduler/runs", params={"schedule_id": s["id"]}, headers=d["h_admin"])).json()
    assert len(hist) >= 1 and hist[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_run_now_dispatches_to_automation(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    s = (await client.post("/api/v1/scheduler", json={
        "name": "sla", "task_type": "run_automation_job", "task_config": {"job_key": "sla_scan"},
        "schedule_kind": "hourly", "time_of_day": "00:15"}, headers=d["h_admin"])).json()
    run = (await client.post(f"/api/v1/scheduler/{s['id']}/run", headers=d["h_admin"])).json()
    assert run["status"] == "success" and "automation_run" in run["result"]


@pytest.mark.asyncio
async def test_enable_disable_and_monitoring(client: AsyncClient, setup: dict):
    d = setup
    s = (await client.post("/api/v1/scheduler", json={
        "name": "m", "task_type": "noop", "schedule_kind": "daily", "time_of_day": "09:00"}, headers=d["h_admin"])).json()
    # disable clears next_run_at
    off = (await client.post(f"/api/v1/scheduler/{s['id']}/enable", json={"enabled": False}, headers=d["h_admin"])).json()
    assert off["is_active"] is False and off["next_run_at"] is None
    on = (await client.post(f"/api/v1/scheduler/{s['id']}/enable", json={"enabled": True}, headers=d["h_admin"])).json()
    assert on["next_run_at"] is not None
    # dashboard + report
    dash = (await client.get("/api/v1/scheduler/dashboard", headers=d["h_admin"])).json()
    assert dash["total"] >= 1 and "upcoming" in dash and "success_rate" in dash
    rep = (await client.get("/api/v1/scheduler/report", headers=d["h_admin"])).json()
    assert "runs" in rep and "skipped" in rep

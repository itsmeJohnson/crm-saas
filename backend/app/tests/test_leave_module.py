import pytest
import uuid
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.notification import Notification
from app.models.attendance import AttendanceRecord
from app.models.calendar_event import Holiday
from app.models.leave import LeaveRequest
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
    org = await org_repo.create({"name": "Leave Org", "slug": "leave-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@lv.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@lv.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@lv.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


def _monday(offset_weeks: int = 2) -> date:
    """A deterministic future Monday, so day counts skip no weekend unexpectedly."""
    today = date.today()
    d = today + timedelta(days=offset_weeks * 7)
    return d - timedelta(days=d.weekday())  # back to Monday of that week


async def _mk_type(client, headers, **over):
    payload = {"name": "Casual", "code": "CL", "annual_quota": 12, "requires_approval": True}
    payload.update(over)
    return await client.post("/api/v1/leaves/types", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_leave_type_permissions_and_uniqueness(client: AsyncClient, setup: dict):
    data = setup
    assert (await _mk_type(client, data["h_emp"])).status_code == 403
    assert (await _mk_type(client, data["h_mgr"])).status_code == 403
    t = (await _mk_type(client, data["h_admin"])).json()
    assert t["annual_quota"] == 12 and t["requires_approval"] is True
    assert (await _mk_type(client, data["h_admin"])).status_code == 409  # dup code
    # employee can list active types
    types = (await client.get("/api/v1/leaves/types", headers=data["h_emp"])).json()
    assert any(x["id"] == t["id"] for x in types)


@pytest.mark.asyncio
async def test_balance_allocation_and_computation(client: AsyncClient, setup: dict):
    data = setup
    t = (await _mk_type(client, data["h_admin"])).json()
    year = date.today().year
    # admin allocates 10 days
    r = await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "year": year, "allocated": 10}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["allocated"] == 10.0 and r.json()["available"] == 10.0
    # employee sees their own balances
    bals = (await client.get("/api/v1/leaves/balances", headers=data["h_emp"])).json()
    row = next(b for b in bals if b["leave_type_id"] == t["id"])
    assert row["available"] == 10.0
    # employee cannot allocate
    assert (await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "allocated": 5}, headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_apply_approve_marks_attendance_and_balance(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    t = (await _mk_type(client, data["h_admin"])).json()
    await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "allocated": 10}, headers=data["h_admin"])
    mon = _monday(2)
    tue = mon + timedelta(days=1)
    # employee applies for Mon-Tue (2 working days)
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": tue.isoformat(), "reason": "trip"}, headers=data["h_emp"])
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["day_count"] == 2.0 and req["status"] == "pending"
    # pending is reserved in balance
    bals = (await client.get("/api/v1/leaves/balances", headers=data["h_emp"])).json()
    row = next(b for b in bals if b["leave_type_id"] == t["id"])
    assert row["pending"] == 2.0 and row["available"] == 8.0
    # approver notified
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.title == "Leave request to review"))).scalars().first()
    assert notif is not None
    # employee cannot approve own; manager approves
    assert (await client.post(f"/api/v1/leaves/requests/{req['id']}/review",
                              json={"approve": True}, headers=data["h_emp"])).status_code == 403
    r = await client.post(f"/api/v1/leaves/requests/{req['id']}/review",
                          json={"approve": True}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # attendance stamped on_leave for both days
    recs = (await db.execute(select(AttendanceRecord).filter(
        AttendanceRecord.user_id == data["emp"].id, AttendanceRecord.status == "on_leave"))).scalars().all()
    assert len(recs) == 2
    # balance now used
    bals = (await client.get("/api/v1/leaves/balances", headers=data["h_emp"])).json()
    row = next(b for b in bals if b["leave_type_id"] == t["id"])
    assert row["used"] == 2.0 and row["pending"] == 0.0 and row["available"] == 8.0
    # requester notified
    dec = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.title == "Leave approved"))).scalars().first()
    assert dec is not None


@pytest.mark.asyncio
async def test_insufficient_balance_and_overlap_and_half_day(client: AsyncClient, setup: dict):
    data = setup
    t = (await _mk_type(client, data["h_admin"], annual_quota=1)).json()
    await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "allocated": 1}, headers=data["h_admin"])
    mon = _monday(3)
    # 3 working days but only 1 allocated → rejected
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": (mon + timedelta(days=2)).isoformat()}, headers=data["h_emp"])
    assert r.status_code == 400 and "Insufficient balance" in r.text
    # half day = 0.5 day, fits in 1 allocated
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"], "start_date": mon.isoformat(),
        "end_date": mon.isoformat(), "is_half_day": True, "half_day_period": "first_half"}, headers=data["h_emp"])
    assert r.status_code == 201 and r.json()["day_count"] == 0.5
    # overlapping request on the same day → 409
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": mon.isoformat()}, headers=data["h_emp"])
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_wfh_no_balance_and_holiday_excluded_in_count(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    mon = _monday(4)
    # a holiday on Tuesday
    db.add(Holiday(organization_id=data["org"].id, name="Festival", holiday_date=mon + timedelta(days=1),
                   created_by=data["admin"].id))
    await db.commit()
    # WFH Mon-Wed: Tue is a holiday → 2 working days, needs no leave type/balance
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "wfh", "start_date": mon.isoformat(),
        "end_date": (mon + timedelta(days=2)).isoformat(), "reason": "remote"}, headers=data["h_emp"])
    assert r.status_code == 201, r.text
    assert r.json()["day_count"] == 2.0 and r.json()["request_type"] == "wfh"


@pytest.mark.asyncio
async def test_auto_approve_type_and_reject_flow(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # a type that does not require approval → auto-approved on apply
    t = (await _mk_type(client, data["h_admin"], name="Comp Off", code="CO",
                        requires_approval=False, deducts_balance=False)).json()
    mon = _monday(5)
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": mon.isoformat()}, headers=data["h_emp"])
    assert r.status_code == 201 and r.json()["status"] == "approved"

    # a normal type + reject flow
    t2 = (await _mk_type(client, data["h_admin"])).json()
    await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t2["id"], "allocated": 5}, headers=data["h_admin"])
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t2["id"],
        "start_date": (mon + timedelta(days=1)).isoformat(), "end_date": (mon + timedelta(days=1)).isoformat()}, headers=data["h_emp"])
    rid = r.json()["id"]
    r = await client.post(f"/api/v1/leaves/requests/{rid}/review", json={"approve": False, "note": "busy week"}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    # rejected does not consume balance
    bals = (await client.get("/api/v1/leaves/balances", headers=data["h_emp"])).json()
    row = next(b for b in bals if b["leave_type_id"] == t2["id"])
    assert row["used"] == 0.0 and row["available"] == 5.0


@pytest.mark.asyncio
async def test_cancel_restores_attendance(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    t = (await _mk_type(client, data["h_admin"])).json()
    await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "allocated": 10}, headers=data["h_admin"])
    mon = _monday(6)
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": mon.isoformat()}, headers=data["h_emp"])
    rid = r.json()["id"]
    await client.post(f"/api/v1/leaves/requests/{rid}/review", json={"approve": True}, headers=data["h_mgr"])
    assert (await db.execute(select(AttendanceRecord).filter(
        AttendanceRecord.user_id == data["emp"].id, AttendanceRecord.work_date == mon,
        AttendanceRecord.status == "on_leave", AttendanceRecord.is_deleted == False))).scalars().first() is not None
    # employee cancels → attendance on_leave record removed
    r = await client.post(f"/api/v1/leaves/requests/{rid}/cancel", headers=data["h_emp"])
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await db.execute(select(AttendanceRecord).filter(
        AttendanceRecord.user_id == data["emp"].id, AttendanceRecord.work_date == mon,
        AttendanceRecord.status == "on_leave", AttendanceRecord.is_deleted == False))).scalars().first() is None


@pytest.mark.asyncio
async def test_calendar_dashboard_report_and_workflow(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    t = (await _mk_type(client, data["h_admin"])).json()
    await client.post("/api/v1/leaves/balances/allocate", json={
        "user_id": str(data["emp"].id), "leave_type_id": t["id"], "allocated": 10}, headers=data["h_admin"])

    # workflow rule on leave_applied → notify the manager
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Leave alert", "trigger_event": "leave_applied", "conditions": [],
        "actions": [{"type": "notify_manager", "message": "New leave request"}]}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text

    mon = _monday(7)
    r = await client.post("/api/v1/leaves/requests", json={
        "request_type": "leave", "leave_type_id": t["id"],
        "start_date": mon.isoformat(), "end_date": mon.isoformat()}, headers=data["h_emp"])
    rid = r.json()["id"]
    # workflow fired → manager got a "Workflow: Leave alert" notification
    wf = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "leave",
        Notification.title == "Workflow: Leave alert"))).scalars().first()
    assert wf is not None
    await client.post(f"/api/v1/leaves/requests/{rid}/review", json={"approve": True}, headers=data["h_mgr"])

    # leave calendar (org) shows the approved leave in the month
    first = mon.replace(day=1)
    last = (first + timedelta(days=40)).replace(day=1) - timedelta(days=1)
    cal = (await client.get("/api/v1/leaves/calendar", params={
        "date_from": first.isoformat(), "date_to": last.isoformat()}, headers=data["h_mgr"])).json()
    assert any(c["type"] == "leave" and c["user_name"] == "Emp Two" for c in cal)

    # manager dashboard shows pending_approvals count structure + who is on leave today handled
    dash = (await client.get("/api/v1/leaves/dashboard", headers=data["h_mgr"])).json()
    assert "pending_approvals" in dash and "on_leave_today" in dash

    # report for the year lists the employee with used days
    rep = (await client.get("/api/v1/leaves/report", params={"year": mon.year}, headers=data["h_admin"])).json()
    row = next(r for r in rep["rows"] if r["user_id"] == str(data["emp"].id))
    assert row["used"] == 1.0

    # invalid workflow action for leave entity rejected
    bad = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad", "trigger_event": "leave_approved", "conditions": [],
        "actions": [{"type": "set_status", "value": "x"}]}, headers=data["h_admin"])
    assert bad.status_code == 400

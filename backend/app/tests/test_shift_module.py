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
from app.models.attendance import AttendanceRecord, Shift
from app.models.calendar_event import Holiday
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
    org = await org_repo.create({"name": "Shift Org", "slug": "shift-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@sh.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@sh.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@sh.com", "hashed_password": get_password_hash("password123"),
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
    d = date.today() + timedelta(days=offset_weeks * 7)
    return d - timedelta(days=d.weekday())


async def _mk(client, headers, **over):
    payload = {"name": "General", "code": "GEN", "start_time": "09:00", "end_time": "18:00",
               "shift_type": "general", "break_minutes": 60, "grace_minutes": 10}
    payload.update(over)
    return await client.post("/api/v1/shifts", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_shift_crud_types_and_presets(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # only OrgAdmin manages shifts
    assert (await _mk(client, data["h_emp"])).status_code == 403
    assert (await _mk(client, data["h_mgr"])).status_code == 403
    s = (await _mk(client, data["h_admin"])).json()
    assert s["shift_type"] == "general" and s["is_flexible"] is False
    assert (await _mk(client, data["h_admin"])).status_code == 409  # dup code
    # invalid shift_type rejected
    assert (await _mk(client, data["h_admin"], name="X", code="X", shift_type="lunar")).status_code == 422
    # presets create Morning/Evening/Night/Flexible (skips existing)
    r = await client.post("/api/v1/shifts/presets", json={}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["created"] == 4
    kinds = {x["shift_type"] for x in (await client.get("/api/v1/shifts", headers=data["h_admin"])).json()}
    assert {"morning", "evening", "night", "flexible"}.issubset(kinds)
    # night preset flagged as night shift; flexible flagged flexible
    shifts = (await client.get("/api/v1/shifts", params={"shift_type": "night"}, headers=data["h_admin"])).json()
    assert shifts[0]["is_night_shift"] is True
    # re-running presets creates none (idempotent)
    assert (await client.post("/api/v1/shifts/presets", json={}, headers=data["h_admin"])).json()["created"] == 0


@pytest.mark.asyncio
async def test_flexible_shift_skips_late_and_early(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    flex = (await _mk(client, data["h_admin"], name="Flexi", code="FLX", shift_type="flexible")).json()
    assert flex["is_flexible"] is True
    await client.post("/api/v1/shifts/assign", json={
        "shift_id": flex["id"], "user_ids": [str(data["emp"].id)], "start_date": "2020-01-01"}, headers=data["h_admin"])
    # a late biometric punch on a flexible shift must NOT be flagged late
    r = await client.post("/api/v1/attendance/biometric/punch", json={
        "user_id": str(data["emp"].id), "type": "in", "timestamp": "2026-07-06T06:00:00Z"}, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["is_late"] is False and r.json()["status"] == "present"
    # early clock-out also not flagged
    r = await client.post("/api/v1/attendance/biometric/punch", json={
        "user_id": str(data["emp"].id), "type": "out", "timestamp": "2026-07-06T09:00:00Z"}, headers=data["h_admin"])
    assert r.json()["is_early_logout"] is False


@pytest.mark.asyncio
async def test_rotation_crud_and_shift_resolution(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    morning = (await _mk(client, data["h_admin"], name="Morning", code="M", start_time="06:00", end_time="14:00", shift_type="morning")).json()
    evening = (await _mk(client, data["h_admin"], name="Evening", code="E", start_time="14:00", end_time="22:00", shift_type="evening")).json()
    # need >= 2 shifts
    assert (await client.post("/api/v1/shifts/rotations", json={
        "name": "Bad", "shift_sequence": [morning["id"]], "rotation_days": 7}, headers=data["h_admin"])).status_code == 422
    r = await client.post("/api/v1/shifts/rotations", json={
        "name": "Weekly", "code": "WK", "shift_sequence": [morning["id"], evening["id"]], "rotation_days": 7}, headers=data["h_admin"])
    assert r.status_code == 201, r.text
    rot = r.json()
    assert rot["shift_names"] == ["Morning", "Evening"] and rot["rotation_days"] == 7

    # assign the employee with a Monday anchor
    anchor = _monday(2)
    r = await client.post(f"/api/v1/shifts/rotations/{rot['id']}/assign", json={
        "user_ids": [str(data["emp"].id)], "anchor_date": anchor.isoformat()}, headers=data["h_admin"])
    assert r.json()["assigned"] == 1
    # employee notified
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.category == "shift"))).scalars().first() is not None

    # resolution: week 0 = Morning, week 1 = Evening (via attendance clock-in shift_id)
    from app.services.shift_service import ShiftService
    svc = ShiftService(db)
    s0 = await svc.resolve_shift_for_user(data["org"].id, data["emp"].id, anchor)
    s1 = await svc.resolve_shift_for_user(data["org"].id, data["emp"].id, anchor + timedelta(days=7))
    assert s0 and s0.name == "Morning"
    assert s1 and s1.name == "Evening"

    # deleting a shift used by a rotation is blocked
    assert (await client.delete(f"/api/v1/shifts/{morning['id']}", headers=data["h_admin"])).status_code == 409

    # members list + remove
    members = (await client.get(f"/api/v1/shifts/rotations/{rot['id']}/members", headers=data["h_admin"])).json()
    assert members[0]["user_name"] == "Emp Two"
    r = await client.post(f"/api/v1/shifts/rotations/{rot['id']}/members/remove",
                          params={"user_id": str(data["emp"].id)}, headers=data["h_admin"])
    assert r.json()["removed"] == 1


@pytest.mark.asyncio
async def test_direct_assignment_beats_rotation_in_calendar(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    morning = (await _mk(client, data["h_admin"], name="Morning", code="M", start_time="06:00", end_time="14:00",
                         shift_type="morning", working_days=["mon", "tue", "wed", "thu", "fri"])).json()
    mon = _monday(2)
    sat = mon + timedelta(days=5)
    await client.post("/api/v1/shifts/assign", json={
        "shift_id": morning["id"], "user_ids": [str(data["emp"].id)], "start_date": mon.isoformat()}, headers=data["h_admin"])
    # a holiday on Tuesday
    db.add(Holiday(organization_id=data["org"].id, name="Festival", holiday_date=mon + timedelta(days=1),
                   created_by=data["admin"].id))
    await db.commit()

    cal = (await client.get("/api/v1/shifts/calendar", params={
        "date_from": mon.isoformat(), "date_to": (mon + timedelta(days=6)).isoformat(),
        "user_id": str(data["emp"].id)}, headers=data["h_admin"])).json()
    by_date = {c["date"]: c for c in cal}
    assert by_date[mon.isoformat()]["state"] == "working" and by_date[mon.isoformat()]["shift_name"] == "Morning"
    assert by_date[(mon + timedelta(days=1)).isoformat()]["state"] == "holiday"   # Tue holiday
    assert by_date[sat.isoformat()]["state"] == "weekly_off"                       # Sat not a working day


@pytest.mark.asyncio
async def test_shift_attendance_and_reports(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    shift = (await _mk(client, data["h_admin"], start_time="09:00", end_time="18:00")).json()
    sid = uuid.UUID(shift["id"])
    await client.post("/api/v1/shifts/assign", json={
        "shift_id": shift["id"], "user_ids": [str(data["emp"].id)], "start_date": "2020-01-01"}, headers=data["h_admin"])
    # seed attendance records against the shift
    db.add(AttendanceRecord(organization_id=data["org"].id, user_id=data["emp"].id, work_date=date(2026, 5, 4),
                            shift_id=sid, status="present", worked_minutes=480,
                            clock_in_at=None))
    rec2 = AttendanceRecord(organization_id=data["org"].id, user_id=data["emp"].id, work_date=date(2026, 5, 5),
                            shift_id=sid, status="late", is_late=True, late_minutes=15, worked_minutes=400)
    db.add(rec2)
    await db.commit()
    # mark rec present via clock_in flag by setting clock_in_at
    rec2.clock_in_at = None
    await db.commit()

    att = (await client.get(f"/api/v1/shifts/{shift['id']}/attendance", params={
        "date_from": "2026-05-01", "date_to": "2026-05-31"}, headers=data["h_admin"])).json()
    assert att["shift_name"] == "General" and len(att["records"]) == 2

    rep = (await client.get("/api/v1/shifts/reports", params={
        "date_from": "2026-05-01", "date_to": "2026-05-31"}, headers=data["h_admin"])).json()
    row = next(r for r in rep if r["shift_id"] == shift["id"])
    assert row["records"] == 2 and row["late"] == 1 and row["assigned"] == 1


@pytest.mark.asyncio
async def test_dashboard_and_workflow_shift_assigned(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    shift = (await _mk(client, data["h_admin"], shift_type="morning")).json()
    # workflow rule on shift_assigned → notify the assigned user
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Shift alert", "trigger_event": "shift_assigned", "conditions": [],
        "actions": [{"type": "notify_user", "message": "You have a new shift"}]}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text
    await client.post("/api/v1/shifts/assign", json={
        "shift_id": shift["id"], "user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    wf = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.category == "shift",
        Notification.title == "Workflow: Shift alert"))).scalars().first()
    assert wf is not None

    dash = (await client.get("/api/v1/shifts/dashboard", headers=data["h_admin"])).json()
    assert dash["total_shifts"] >= 1 and "by_type" in dash

    # invalid action type for shift entity rejected
    bad = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad", "trigger_event": "shift_assigned", "conditions": [],
        "actions": [{"type": "set_status", "value": "x"}]}, headers=data["h_admin"])
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_attendance_regression_direct_shift_still_flags_late(client: AsyncClient, setup: dict, db: AsyncSession):
    """The delegation to ShiftService must preserve fixed-shift late detection."""
    data = setup
    shift = (await _mk(client, data["h_admin"], start_time="09:00", end_time="18:00", grace_minutes=10)).json()
    await client.post("/api/v1/shifts/assign", json={
        "shift_id": shift["id"], "user_ids": [str(data["emp"].id)], "start_date": "2020-01-01"}, headers=data["h_admin"])
    # 09:30 IST (04:00 UTC) is 30 min late on a fixed shift
    r = await client.post("/api/v1/attendance/biometric/punch", json={
        "user_id": str(data["emp"].id), "type": "in", "timestamp": "2026-07-06T04:00:00Z"}, headers=data["h_admin"])
    assert r.json()["is_late"] is True and r.json()["late_minutes"] == 30

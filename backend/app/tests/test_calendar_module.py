import pytest
from datetime import datetime, timezone, timedelta, date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.activity import Activity
from app.models.task import Task
from app.models.notification import Notification


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Cal Org", "slug": "cal-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@cal.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@cal.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"}}


def _iso(dt): return dt.isoformat()


@pytest.mark.asyncio
async def test_event_crud_and_notify(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    res = await client.post("/api/v1/calendar/events", json={
        "title": "Kickoff", "event_type": "Meeting", "location": "Zoom",
        "start_at": _iso(now + timedelta(hours=1)), "end_at": _iso(now + timedelta(hours=2)),
        "assigned_user_id": str(data["emp"].id), "attendees": [{"user_id": str(data["emp"].id), "name": "Emp"}]},
        headers=data["headers"])
    assert res.status_code == 201
    eid = res.json()["id"]
    # attendee notified
    n = await db.execute(select(Notification).filter(Notification.user_id == data["emp"].id, Notification.category == "calendar"))
    assert n.scalars().first() is not None
    # update + delete
    upd = await client.patch(f"/api/v1/calendar/events/{eid}", json={"status": "Completed"}, headers=data["headers"])
    assert upd.json()["status"] == "Completed"
    d = await client.delete(f"/api/v1/calendar/events/{eid}", headers=data["headers"])
    assert d.status_code == 204


@pytest.mark.asyncio
async def test_end_before_start_rejected(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    res = await client.post("/api/v1/calendar/events", json={
        "title": "Bad", "start_at": _iso(now + timedelta(hours=2)), "end_at": _iso(now + timedelta(hours=1))},
        headers=data["headers"])
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_unified_calendar_aggregates(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    # event
    await client.post("/api/v1/calendar/events", json={
        "title": "Demo", "start_at": _iso(now + timedelta(hours=1)), "end_at": _iso(now + timedelta(hours=2))}, headers=data["headers"])
    # task due within range
    db.add(Task(organization_id=data["org"].id, title="Do it", due_date=now + timedelta(hours=3), created_by=data["admin"].id))
    # activity meeting
    db.add(Activity(organization_id=data["org"].id, activity_type="Meeting", subject="Sync",
                    status="Planned", due_date=now + timedelta(hours=4), created_by=data["admin"].id))
    await db.commit()
    # holiday today
    await client.post("/api/v1/calendar/holidays", json={"name": "Founders Day", "holiday_date": now.date().isoformat()}, headers=data["headers"])

    res = await client.get("/api/v1/calendar/", params={
        "date_from": _iso(now - timedelta(days=1)), "date_to": _iso(now + timedelta(days=1))}, headers=data["headers"])
    assert res.status_code == 200
    sources = {i["source"] for i in res.json()}
    assert {"event", "task", "activity", "holiday"} <= sources


@pytest.mark.asyncio
async def test_recurring_event_expands(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now + timedelta(days=1)
    await client.post("/api/v1/calendar/events", json={
        "title": "Daily standup", "start_at": _iso(start), "end_at": _iso(start + timedelta(minutes=15)),
        "recurrence": "daily", "recurrence_until": (now + timedelta(days=6)).date().isoformat()}, headers=data["headers"])
    res = await client.get("/api/v1/calendar/", params={
        "date_from": _iso(now), "date_to": _iso(now + timedelta(days=10))}, headers=data["headers"])
    occurrences = [i for i in res.json() if i["title"] == "Daily standup"]
    # ~6 daily occurrences within the until window
    assert 5 <= len(occurrences) <= 6


@pytest.mark.asyncio
async def test_holidays_and_working_hours(client: AsyncClient, setup: dict):
    data = setup
    h = await client.post("/api/v1/calendar/holidays", json={"name": "New Year", "holiday_date": "2026-01-01", "recurring_annual": True}, headers=data["headers"])
    assert h.status_code == 201
    lst = await client.get("/api/v1/calendar/holidays", headers=data["headers"])
    assert any(x["name"] == "New Year" for x in lst.json())
    await client.delete(f"/api/v1/calendar/holidays/{h.json()['id']}", headers=data["headers"])

    wh = await client.get("/api/v1/calendar/working-hours", headers=data["headers"])
    assert wh.status_code == 200
    assert wh.json()["days"]["mon"]["enabled"] is True
    upd = await client.patch("/api/v1/calendar/working-hours", json={"timezone": "America/New_York"}, headers=data["headers"])
    assert upd.json()["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_ics_feed(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    await client.post("/api/v1/calendar/events", json={
        "title": "Feed event", "start_at": _iso(now + timedelta(hours=1)), "end_at": _iso(now + timedelta(hours=2))}, headers=data["headers"])
    fu = await client.get("/api/v1/calendar/feed-url", headers=data["headers"])
    assert fu.status_code == 200
    token = fu.json()["token"]
    # public feed (no auth)
    feed = await client.get(f"/api/v1/calendar/feed/{token}.ics")
    assert feed.status_code == 200
    assert "text/calendar" in feed.headers["content-type"]
    assert "BEGIN:VCALENDAR" in feed.text
    assert "SUMMARY:Feed event" in feed.text
    # bad token -> 404
    bad = await client.get("/api/v1/calendar/feed/nope.ics")
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_reminder_cron(client: AsyncClient, db: AsyncSession, setup: dict):
    from app.cron.lead_cron import dispatch_event_reminders
    data = setup
    now = datetime.now(timezone.utc)
    await client.post("/api/v1/calendar/events", json={
        "title": "Remind", "start_at": _iso(now + timedelta(hours=2)), "end_at": _iso(now + timedelta(hours=3)),
        "remind_at": _iso(now - timedelta(minutes=5)), "assigned_user_id": str(data["emp"].id)}, headers=data["headers"])
    sent = await dispatch_event_reminders(db)
    await db.commit()
    assert sent >= 1
    assert await dispatch_event_reminders(db) == 0


@pytest.mark.asyncio
async def test_reports(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    await client.post("/api/v1/calendar/events", json={
        "title": "R1", "event_type": "Meeting", "start_at": _iso(now + timedelta(days=1)), "end_at": _iso(now + timedelta(days=1, hours=1))}, headers=data["headers"])
    res = await client.get("/api/v1/calendar/reports", headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["total_events"] == 1
    assert res.json()["upcoming_7d"] == 1


@pytest.mark.asyncio
async def test_scoping(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    emp_headers = {"Authorization": f"Bearer {create_access_token(data['emp'].id)}"}
    # admin-only event (assigned to admin)
    await client.post("/api/v1/calendar/events", json={
        "title": "Admin private", "start_at": _iso(now + timedelta(hours=1)), "end_at": _iso(now + timedelta(hours=2))}, headers=data["headers"])
    res = await client.get("/api/v1/calendar/", params={
        "date_from": _iso(now - timedelta(days=1)), "date_to": _iso(now + timedelta(days=1))}, headers=emp_headers)
    assert not any(i["title"] == "Admin private" for i in res.json())

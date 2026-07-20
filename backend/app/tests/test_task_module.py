import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.task import Task
from app.models.notification import Notification


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Task Org", "slug": "task-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@task.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@task.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "emp_headers": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_create_assign_notify(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    res = await client.post("/api/v1/tasks/", json={
        "title": "Call client", "priority": "High", "assigned_user_id": str(data["emp"].id),
        "checklist": [{"text": "Prep deck"}, {"text": "Send agenda"}]}, headers=data["headers"])
    assert res.status_code == 201
    body = res.json()
    assert body["priority"] == "High"
    assert body["status"] == "Todo"
    assert len(body["checklist"]) == 2 and body["checklist"][0]["id"]
    n = await db.execute(select(Notification).filter(Notification.user_id == data["emp"].id, Notification.category == "task"))
    assert n.scalars().first() is not None


@pytest.mark.asyncio
async def test_checklist_toggle(client: AsyncClient, setup: dict):
    data = setup
    t = (await client.post("/api/v1/tasks/", json={"title": "T", "checklist": [{"text": "step 1"}]}, headers=data["headers"])).json()
    item_id = t["checklist"][0]["id"]
    res = await client.patch(f"/api/v1/tasks/{t['id']}/checklist", json={"item_id": item_id, "done": True}, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["checklist"][0]["done"] is True


@pytest.mark.asyncio
async def test_recurring_spawns_next(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    due = datetime.now(timezone.utc).isoformat()
    t = (await client.post("/api/v1/tasks/", json={"title": "Daily standup", "recurrence": "daily", "due_date": due}, headers=data["headers"])).json()
    res = await client.post(f"/api/v1/tasks/{t['id']}/complete", headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["status"] == "Done"
    # a new occurrence exists
    rows = (await db.execute(select(Task).filter(Task.organization_id == data["org"].id, Task.status == "Todo", Task.recurrence == "daily"))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_dependencies_block_completion_and_cycle_guard(client: AsyncClient, setup: dict):
    data = setup
    a = (await client.post("/api/v1/tasks/", json={"title": "A"}, headers=data["headers"])).json()
    b = (await client.post("/api/v1/tasks/", json={"title": "B"}, headers=data["headers"])).json()
    # A depends on B
    dep = await client.post(f"/api/v1/tasks/{a['id']}/dependencies", json={"depends_on_task_id": b["id"]}, headers=data["headers"])
    assert dep.status_code == 201
    # cannot complete A while B open
    blocked = await client.post(f"/api/v1/tasks/{a['id']}/complete", headers=data["headers"])
    assert blocked.status_code == 400
    # cycle guard: B depends on A -> rejected
    cyc = await client.post(f"/api/v1/tasks/{b['id']}/dependencies", json={"depends_on_task_id": a["id"]}, headers=data["headers"])
    assert cyc.status_code == 400
    # complete B, then A completes
    await client.post(f"/api/v1/tasks/{b['id']}/complete", headers=data["headers"])
    ok = await client.post(f"/api/v1/tasks/{a['id']}/complete", headers=data["headers"])
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_comments(client: AsyncClient, setup: dict):
    data = setup
    t = (await client.post("/api/v1/tasks/", json={"title": "T"}, headers=data["headers"])).json()
    c = await client.post(f"/api/v1/tasks/{t['id']}/comments", json={"body": "Working on it"}, headers=data["headers"])
    assert c.status_code == 201
    lst = await client.get(f"/api/v1/tasks/{t['id']}/comments", headers=data["headers"])
    assert len(lst.json()) == 1


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.asyncio
async def test_attachments(client: AsyncClient, setup: dict):
    data = setup
    t = (await client.post("/api/v1/tasks/", json={"title": "T"}, headers=data["headers"])).json()
    up = await client.post(f"/api/v1/tasks/{t['id']}/attachments", files={"file": ("a.png", PNG, "image/png")}, headers=data["headers"])
    assert up.status_code == 201
    lst = await client.get(f"/api/v1/tasks/{t['id']}/attachments", headers=data["headers"])
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_bulk_and_filters(client: AsyncClient, setup: dict):
    data = setup
    ids = []
    for i in range(3):
        ids.append((await client.post("/api/v1/tasks/", json={"title": f"T{i}", "priority": "Low"}, headers=data["headers"])).json()["id"])
    res = await client.post("/api/v1/tasks/bulk-update", json={"task_ids": ids, "fields": {"priority": "Urgent", "status": "InProgress"}}, headers=data["headers"])
    assert res.json()["affected_count"] == 3
    lst = await client.get("/api/v1/tasks/?priority=Urgent", headers=data["headers"])
    assert len(lst.json()) == 3
    d = await client.post("/api/v1/tasks/bulk-delete", json={"task_ids": ids[:2]}, headers=data["headers"])
    assert d.json()["affected_count"] == 2


@pytest.mark.asyncio
async def test_reports_and_calendar(client: AsyncClient, setup: dict):
    data = setup
    now = datetime.now(timezone.utc)
    # due later today (not overdue): pin to noon UTC today so it stays within today's window and in the future-ish
    due_today = now.replace(hour=23, minute=0, second=0, microsecond=0)
    await client.post("/api/v1/tasks/", json={"title": "Due today", "due_date": due_today.isoformat()}, headers=data["headers"])
    overdue = await client.post("/api/v1/tasks/", json={"title": "Late", "due_date": (now - timedelta(days=2)).isoformat()}, headers=data["headers"])
    done = (await client.post("/api/v1/tasks/", json={"title": "Fin"}, headers=data["headers"])).json()
    await client.post(f"/api/v1/tasks/{done['id']}/complete", headers=data["headers"])

    rep = await client.get("/api/v1/tasks/reports", headers=data["headers"])
    assert rep.status_code == 200
    body = rep.json()
    assert body["total"] == 3
    assert body["completed"] == 1
    assert body["overdue"] == 1
    assert body["due_today"] == 1

    cal = await client.get("/api/v1/tasks/calendar", params={
        "date_from": (now - timedelta(days=5)).isoformat(), "date_to": (now + timedelta(days=5)).isoformat()},
        headers=data["headers"])
    assert cal.status_code == 200
    assert len(cal.json()) >= 2


@pytest.mark.asyncio
async def test_scoping_non_admin_sees_own(client: AsyncClient, setup: dict):
    data = setup
    # admin creates a task assigned to nobody (self)
    await client.post("/api/v1/tasks/", json={"title": "Admin only"}, headers=data["headers"])
    # emp creates their own
    await client.post("/api/v1/tasks/", json={"title": "Emp task"}, headers=data["emp_headers"])
    emp_list = await client.get("/api/v1/tasks/", headers=data["emp_headers"])
    titles = [t["title"] for t in emp_list.json()]
    assert "Emp task" in titles
    assert "Admin only" not in titles


@pytest.mark.asyncio
async def test_reminder_cron(client: AsyncClient, db: AsyncSession, setup: dict):
    from app.cron.lead_cron import dispatch_task_reminders
    data = setup
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await client.post("/api/v1/tasks/", json={"title": "Remind me", "remind_at": past, "assigned_user_id": str(data["emp"].id)}, headers=data["headers"])
    sent = await dispatch_task_reminders(db)
    await db.commit()
    assert sent == 1
    assert await dispatch_task_reminders(db) == 0  # already reminded


@pytest.mark.asyncio
async def test_task_workflow(client: AsyncClient, setup: dict):
    data = setup
    await client.post("/api/v1/leads/workflows", json={
        "name": "Urgent to InProgress", "trigger_event": "task_created",
        "conditions": [{"field": "priority", "op": "eq", "value": "Urgent"}],
        "actions": [{"type": "set_status", "value": "InProgress"}]}, headers=data["headers"])
    res = await client.post("/api/v1/tasks/", json={"title": "Hot", "priority": "Urgent"}, headers=data["headers"])
    assert res.json()["status"] == "InProgress"

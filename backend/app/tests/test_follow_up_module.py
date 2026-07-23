import uuid
import pytest
from datetime import datetime, timezone, timedelta
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
from app.models.calendar_event import CalendarEvent
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.services.workflow_engine_service import TRIGGER_ENTITY
from app.services.workflow_service import WorkflowService
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


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "FU Org", "slug": "fu-org"})
    await db.commit()
    ur = UserRepository(db)
    manager = await ur.create_user(org.id, {"email": "mgr@fu.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mana", "last_name": "Ger", "role": "Manager", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@fu.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Loyee", "role": "Employee", "is_active": True, "reporting_to_id": manager.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(PipelineStage.organization_id == org.id))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    lead = Lead(organization_id=org.id, first_name="Rahul", last_name="Mehta", title="3BHK enquiry",
                status="New", value=8500000, score=40, priority="High",
                assigned_user_id=emp.id, created_by=emp.id, stage_id=stage.id)
    db.add(lead)
    await db.commit()
    return {"org": org, "manager": manager, "emp": emp, "lead": lead, "stage": stage,
            "h_mgr": {"Authorization": f"Bearer {create_access_token(manager.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- triggers registered ----------
def test_follow_up_triggers_registered():
    for t in ("follow_up_created", "follow_up_missed", "meeting_scheduled", "site_visit_scheduled"):
        assert t in TRIGGER_ENTITY and TRIGGER_ENTITY[t] == "lead"
    assert "follow_up_created" in WorkflowService.VALID_TRIGGERS
    assert "follow_up_missed" in WorkflowService.VALID_TRIGGERS


# ---------- follow-up capture orchestration ----------
@pytest.mark.asyncio
async def test_follow_up_creates_task_activity_and_notifies_manager(client: AsyncClient, setup, db: AsyncSession):
    lead = setup["lead"]
    nxt = (_now() + timedelta(days=1)).isoformat()
    r = await client.post(f"/api/v1/leads/{lead.id}/follow-up", headers=setup["h_emp"], json={
        "outcome": "Interested", "remarks": "Wants a site visit next week", "follow_up_type": "call",
        "next_follow_up_at": nxt, "priority": "High", "reminder_minutes_before": 30})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["outcome"] == "Interested" and body["task_id"] and body["activity_id"]
    assert body["status"] == "Interested" and body["status_changed"] is True  # outcome→status mapping
    assert body["manager_notified"] is True

    # follow-up Task created (lead-linked, reminder set, High priority)
    task = (await db.execute(select(Task).filter(Task.id == uuid.UUID(body["task_id"])))).scalars().first()
    assert task and task.lead_id == lead.id and task.priority == "High"
    assert task.remind_at is not None and task.due_date is not None
    # timeline Activity logged as a Follow-up
    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(body["activity_id"])))).scalars().first()
    assert act and act.activity_type == "Follow-up" and act.call_disposition == "Interested"
    # manager got a notification
    notes = (await db.execute(select(Notification).filter(
        Notification.user_id == setup["manager"].id, Notification.category == "follow_up"))).scalars().all()
    assert len(notes) == 1
    # audit trail
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id, AuditLog.action == "FOLLOW_UP_LOGGED"))).scalars().all()
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_meeting_follow_up_creates_calendar_event(client: AsyncClient, setup, db: AsyncSession):
    lead = setup["lead"]
    nxt = (_now() + timedelta(days=2)).isoformat()
    r = await client.post(f"/api/v1/leads/{lead.id}/follow-up", headers=setup["h_emp"], json={
        "outcome": "Site Visit Scheduled", "follow_up_type": "site_visit",
        "next_follow_up_at": nxt, "priority": "Medium"})
    assert r.status_code == 201
    body = r.json()
    assert body["calendar_event_id"]
    ev = (await db.execute(select(CalendarEvent).filter(
        CalendarEvent.id == uuid.UUID(body["calendar_event_id"])))).scalars().first()
    assert ev and ev.event_type == "Site Visit" and ev.lead_id == lead.id


@pytest.mark.asyncio
async def test_terminal_outcome_needs_no_next_date(client: AsyncClient, setup, db: AsyncSession):
    lead = setup["lead"]
    r = await client.post(f"/api/v1/leads/{lead.id}/follow-up", headers=setup["h_emp"], json={
        "outcome": "Sale Won", "follow_up_type": "call"})
    assert r.status_code == 201
    body = r.json()
    assert body["task_id"] is None  # no next follow-up task for a terminal outcome
    assert body["status"] == "Converted" and body["status_changed"] is True
    # non-terminal without a date → 400
    r2 = await client.post(f"/api/v1/leads/{lead.id}/follow-up", headers=setup["h_emp"], json={
        "outcome": "Follow-up", "follow_up_type": "call"})
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_invalid_outcome_rejected(client: AsyncClient, setup):
    r = await client.post(f"/api/v1/leads/{setup['lead'].id}/follow-up", headers=setup["h_emp"], json={
        "outcome": "Teleport", "next_follow_up_at": (_now() + timedelta(days=1)).isoformat()})
    assert r.status_code == 400


# ---------- work queue ordering & scope ----------
@pytest.mark.asyncio
async def test_work_queue_ordering_and_scope(client: AsyncClient, setup, db: AsyncSession):
    lead = setup["lead"]
    now = _now()
    # an OVERDUE follow-up task (lead-linked)
    db.add(Task(organization_id=setup["org"].id, title="Follow up: overdue", status="Todo", priority="High",
                due_date=now - timedelta(days=1), lead_id=lead.id, assigned_user_id=setup["emp"].id,
                created_by=setup["emp"].id))
    # a TODAY follow-up task
    db.add(Task(organization_id=setup["org"].id, title="Follow up: today", status="Todo", priority="Medium",
                due_date=now + timedelta(hours=2), lead_id=lead.id, assigned_user_id=setup["emp"].id,
                created_by=setup["emp"].id))
    # a personal task (not lead-linked)
    db.add(Task(organization_id=setup["org"].id, title="Submit expenses", status="Todo", priority="Low",
                assigned_user_id=setup["emp"].id, created_by=setup["emp"].id))
    # an upcoming meeting
    db.add(CalendarEvent(organization_id=setup["org"].id, title="Demo call", event_type="Meeting",
                         start_at=now + timedelta(days=1), end_at=now + timedelta(days=1, hours=1),
                         assigned_user_id=setup["emp"].id, created_by=setup["emp"].id, lead_id=lead.id))
    await db.commit()

    r = await client.get("/api/v1/dashboard/work-queue", headers=setup["h_emp"])
    assert r.status_code == 200
    body = r.json()
    keys = [s["key"] for s in body["sections"]]
    assert keys == ["overdue_follow_ups", "todays_follow_ups", "meetings", "site_visits",
                    "hot_leads", "interested_leads", "new_leads", "cold_leads",
                    "closed_leads", "personal_tasks"]
    assert body["counts"]["overdue_follow_ups"] == 1
    assert body["counts"]["todays_follow_ups"] == 1
    assert body["counts"]["meetings"] == 1
    assert body["counts"]["personal_tasks"] == 1
    # next action = the overdue follow-up
    assert body["next_action"] and body["next_action"]["overdue"] is True

    # manager sees the employee's queue (downline scope)
    rm = await client.get("/api/v1/dashboard/work-queue", headers=setup["h_mgr"])
    assert rm.json()["counts"]["overdue_follow_ups"] == 1

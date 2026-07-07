import pytest
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.pipeline import PipelineStage
from app.models.notification import Notification
from app.models.workflow_rule import WorkflowRule
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key: str) -> str | None:
        return storage.get(key)

    async def mock_set(key: str, value: str, ex: int = 300) -> bool:
        storage[key] = value
        return True

    async def mock_delete(key: str) -> bool:
        storage.pop(key, None)
        return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_get_active_features(*args, **kwargs) -> list[str]:
        return ["OUTBOUND_CALLING", "INBOUND_CALLING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_get_active_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Calling Org", "slug": "calling-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@calling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@calling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    await db.commit()
    tl = await user_repo.create_user(org.id, {
        "email": "tl@calling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Tl", "last_name": "One", "role": "Employee", "is_active": True,
        "reporting_to_id": manager.id})
    await db.commit()
    agent = await user_repo.create_user(org.id, {
        "email": "agent@calling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Agent", "last_name": "One", "role": "Employee", "is_active": True,
        "reporting_to_id": tl.id})
    await db.commit()
    agent2 = await user_repo.create_user(org.id, {
        "email": "agent2@calling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Agent", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": tl.id})
    await db.commit()

    # Org creation seeds default pipeline stages; reuse them (unique on org+order_position)
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage)
        await db.commit()
    dropped = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.name == "Dropped"))).scalars().first()
    if not dropped:
        dropped = PipelineStage(organization_id=org.id, name="Dropped", order_position=999)
        db.add(dropped)
        await db.commit()

    lead = Lead(organization_id=org.id, first_name="Cust", last_name="Omer", phone="+919876500001",
                title="Calling Lead", status="New", assigned_user_id=agent.id, created_by=admin.id,
                stage_id=stage.id)
    db.add(lead)
    await db.commit()

    return {
        "org": org, "admin": admin, "manager": manager, "tl": tl, "agent": agent, "agent2": agent2,
        "stage": stage, "lead": lead,
        "headers_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "headers_manager": {"Authorization": f"Bearer {create_access_token(manager.id)}"},
        "headers_tl": {"Authorization": f"Bearer {create_access_token(tl.id)}"},
        "headers_agent": {"Authorization": f"Bearer {create_access_token(agent.id)}"},
        "headers_agent2": {"Authorization": f"Bearer {create_access_token(agent2.id)}"},
    }


def _call(org_id, user_id, lead_id, *, direction="OUTBOUND", disposition=None, status="Completed",
          duration=None, recording=None, tags=None, created_at=None, subject="Call"):
    a = Activity(organization_id=org_id, activity_type="Call", subject=subject,
                 status=status, assigned_user_id=user_id, created_by=user_id, lead_id=lead_id,
                 call_direction=direction, call_disposition=disposition, call_duration=duration,
                 recording_url=recording, call_tags=tags)
    if created_at:
        a.created_at = created_at
    return a


@pytest.mark.asyncio
async def test_history_filters_and_scoping(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    org, lead = data["org"], data["lead"]
    db.add_all([
        _call(org.id, data["agent"].id, lead.id, direction="OUTBOUND", disposition="Picked",
              duration=120, recording="https://rec/1.mp3", tags=["hot"]),
        _call(org.id, data["agent"].id, lead.id, direction="OUTBOUND", disposition="RNR"),
        _call(org.id, data["agent2"].id, lead.id, direction="INBOUND", disposition="Interested", duration=60),
    ])
    await db.commit()

    # Admin sees all three
    r = await client.get("/api/v1/calling/history", headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 3

    # Agent sees only own calls
    r = await client.get("/api/v1/calling/history", headers=data["headers_agent"])
    assert r.json()["total"] == 2
    assert all(i["agent_id"] == str(data["agent"].id) for i in r.json()["items"])

    # direction filter
    r = await client.get("/api/v1/calling/history", params={"direction": "INBOUND"}, headers=data["headers_admin"])
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["disposition"] == "Interested"

    # disposition filter
    r = await client.get("/api/v1/calling/history", params={"disposition": "RNR"}, headers=data["headers_admin"])
    assert r.json()["total"] == 1

    # agent filter
    r = await client.get("/api/v1/calling/history", params={"agent_id": str(data["agent2"].id)}, headers=data["headers_admin"])
    assert r.json()["total"] == 1

    # has_recording + lead title resolution
    r = await client.get("/api/v1/calling/history", params={"has_recording": True}, headers=data["headers_admin"])
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["recording_url"] == "https://rec/1.mp3"
    assert body["items"][0]["lead_title"] == "Calling Lead"

    # tag filter
    r = await client.get("/api/v1/calling/history", params={"tag": "hot"}, headers=data["headers_admin"])
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_call_tags_set_and_list(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    call = _call(data["org"].id, data["agent"].id, data["lead"].id, disposition="Picked")
    db.add(call)
    await db.commit()

    r = await client.patch(f"/api/v1/calling/{call.id}/tags",
                           json={"tags": ["follow-up", "  hot  ", "follow-up", ""]},
                           headers=data["headers_agent"])
    assert r.status_code == 200, r.text
    assert r.json()["tags"] == ["follow-up", "hot"]

    r = await client.get("/api/v1/calling/tags", headers=data["headers_agent"])
    assert set(r.json()) == {"follow-up", "hot"}

    # another agent cannot tag someone else's call (scoped 404)
    r = await client.patch(f"/api/v1/calling/{call.id}/tags", json={"tags": ["x"]},
                           headers=data["headers_agent2"])
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reports_math(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    org, lead = data["org"], data["lead"]
    db.add_all([
        _call(org.id, data["agent"].id, lead.id, disposition="Picked", duration=100),
        _call(org.id, data["agent"].id, lead.id, disposition="RNR"),
        _call(org.id, data["agent"].id, lead.id, disposition="Busy"),
        _call(org.id, data["agent2"].id, lead.id, direction="INBOUND", disposition="Answered / Resolved", duration=200),
        _call(org.id, data["agent2"].id, lead.id, direction="INBOUND", status="Missed"),
    ])
    await db.commit()

    r = await client.get("/api/v1/calling/reports", headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5
    assert body["missed"] == 1
    assert body["dispositioned"] == 4
    assert body["connected"] == 2  # Picked + Answered / Resolved
    assert body["connect_rate"] == 50.0
    assert body["avg_duration"] == 150
    dirs = {b["label"]: b["count"] for b in body["by_direction"]}
    assert dirs == {"OUTBOUND": 3, "INBOUND": 2}
    assert {b["label"] for b in body["by_disposition"]} == {"Picked", "RNR", "Busy", "Answered / Resolved"}
    agents = {b["label"]: b["count"] for b in body["by_agent"]}
    assert agents == {"Agent One": 3, "Agent Two": 2}
    assert sum(b["count"] for b in body["by_day"]) == 5


@pytest.mark.asyncio
async def test_missed_call_detection_and_notification(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    org, lead = data["org"], data["lead"]
    stale = _call(org.id, data["agent"].id, lead.id, direction="INBOUND", status="Planned",
                  created_at=datetime.now(timezone.utc) - timedelta(minutes=30))
    fresh = _call(org.id, data["agent"].id, lead.id, direction="INBOUND", status="Planned",
                  created_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    db.add_all([stale, fresh])
    await db.commit()

    # history lazily sweeps: the stale call becomes Missed, the fresh one stays Planned
    r = await client.get("/api/v1/calling/history", params={"missed_only": True}, headers=data["headers_agent"])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["id"] == str(stale.id)

    await db.refresh(fresh)
    assert fresh.status == "Planned"

    # agent got a missed-call notification
    notifs = (await db.execute(select(Notification).filter(
        Notification.user_id == data["agent"].id, Notification.category == "calling"))).scalars().all()
    assert len(notifs) == 1
    assert "Missed" in notifs[0].title


@pytest.mark.asyncio
async def test_queue_monitor(client: AsyncClient, setup: dict, db: AsyncSession, mock_redis):
    data = setup
    org, lead = data["org"], data["lead"]

    # agent (non-TL employee) is forbidden
    r = await client.get("/api/v1/calling/queue", headers=data["headers_agent"])
    assert r.status_code == 403

    # put agent on an active call (redis state + planned activity)
    from app.services.agent_state_service import AgentStateService
    await AgentStateService().set_agent_state(org.id, data["agent"].id, "ACTIVE_CALLING")
    db.add(_call(org.id, data["agent"].id, lead.id, status="Planned", subject="Outbound Call"))
    await db.commit()

    r = await client.get("/api/v1/calling/queue", headers=data["headers_manager"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pending_queue"] == 1  # one New lead
    by_id = {a["user_id"]: a for a in body["agents"]}
    active = by_id[str(data["agent"].id)]
    assert active["state"] == "ACTIVE_CALLING"
    assert active["current_call"]["lead_title"] == "Calling Lead"
    idle = by_id[str(data["agent2"].id)]
    assert idle["state"] == "IDLE"
    assert idle["current_call"] is None

    # TL also allowed
    r = await client.get("/api/v1/calling/queue", headers=data["headers_tl"])
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_call_disposition_workflow_trigger_and_stamp(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    org, lead, agent = data["org"], data["lead"], data["agent"]
    db.add(WorkflowRule(organization_id=org.id, name="Prioritize dispositioned", trigger_event="call_disposition",
                        is_active=True, conditions=[], actions=[{"type": "set_priority", "value": "High"}],
                        created_by=data["admin"].id))
    db.add(_call(org.id, agent.id, lead.id, status="Planned"))
    await db.commit()

    r = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition",
                          json={"status": "RNR", "remarks": "no answer"}, headers=data["headers_agent"])
    assert r.status_code == 200, r.text

    await db.refresh(lead)
    assert lead.priority == "High"  # workflow fired

    act = (await db.execute(select(Activity).filter(
        Activity.lead_id == lead.id, Activity.activity_type == "Call"))).scalars().first()
    assert act.call_disposition == "RNR"
    assert act.status == "Completed"


@pytest.mark.asyncio
async def test_call_logged_workflow_trigger_via_communication_log(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    org, lead = data["org"], data["lead"]
    db.add(WorkflowRule(organization_id=org.id, name="Tag called leads", trigger_event="call_logged",
                        is_active=True, conditions=[{"field": "status", "op": "eq", "value": "New"}],
                        actions=[{"type": "set_priority", "value": "Urgent"}], created_by=data["admin"].id))
    await db.commit()

    r = await client.post("/api/v1/communications/", json={
        "channel": "Call", "direction": "OUTBOUND", "subject": "Manual call log",
        "lead_id": str(lead.id)}, headers=data["headers_admin"])
    assert r.status_code == 201, r.text

    await db.refresh(lead)
    assert lead.priority == "Urgent"


@pytest.mark.asyncio
async def test_workflow_crud_accepts_call_triggers(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Call rule", "trigger_event": "call_logged",
        "conditions": [], "actions": [{"type": "set_status", "value": "Contacted"}]},
        headers=data["headers_admin"])
    assert r.status_code == 201, r.text

    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad rule", "trigger_event": "call_answered",
        "conditions": [], "actions": []}, headers=data["headers_admin"])
    assert r.status_code == 400

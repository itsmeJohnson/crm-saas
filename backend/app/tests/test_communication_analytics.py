import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.pipeline import PipelineStage
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
        return ["LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


BASE = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)  # a Monday 10:00


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "CA Org", "slug": "ca-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@ca.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    a1 = await user_repo.create_user(org.id, {
        "email": "a1@ca.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Agent", "last_name": "One", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    a2 = await user_repo.create_user(org.id, {
        "email": "a2@ca.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Agent", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()

    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()

    lead = Lead(organization_id=org.id, first_name="Cust", last_name="Omer", email="cust@x.com", phone="+91900",
                title="Lead", status="Won", value=5000, assigned_user_id=a1.id, created_by=admin.id, stage_id=stage.id)
    contact = Contact(organization_id=org.id, first_name="Con", last_name="Tact", email="con@x.com", created_by=admin.id)
    db.add_all([lead, contact])
    await db.commit()

    def act(channel, direction, agent, minutes, **kw):
        a = Activity(organization_id=org.id, activity_type=channel, subject=f"{channel}", status=kw.get("status", "Completed"),
                     call_direction=direction, assigned_user_id=agent.id, created_by=agent.id,
                     lead_id=kw.get("lead_id", lead.id), contact_id=kw.get("contact_id"),
                     call_duration=kw.get("call_duration"), call_disposition=kw.get("call_disposition"),
                     sms_status=kw.get("sms_status"), wa_status=kw.get("wa_status"),
                     email_status=kw.get("email_status"), email_open_count=kw.get("email_open_count", 0),
                     email_click_count=kw.get("email_click_count", 0))
        a.created_at = BASE + timedelta(minutes=minutes)
        return a

    acts = [
        # inbound SMS at t=0 from lead, agent1 replies outbound SMS at t=5 (response time 300s)
        act("SMS", "INBOUND", a1, 0, sms_status="received"),
        act("SMS", "OUTBOUND", a1, 5, sms_status="delivered"),
        # a call by agent1, 120s talk, connected
        act("Call", "OUTBOUND", a1, 10, call_duration=120, call_disposition="Picked"),
        # a missed call
        act("Call", "INBOUND", a1, 15, status="Missed"),
        # email by agent2, opened + clicked
        act("Email", "OUTBOUND", a2, 20, email_status="sent", email_open_count=2, email_click_count=1, contact_id=contact.id, lead_id=None),
        # failed whatsapp by agent2 (standalone — not attached to the lead)
        act("WhatsApp", "OUTBOUND", a2, 25, wa_status="failed", lead_id=None),
    ]
    db.add_all(acts)
    await db.commit()

    return {
        "org": org, "admin": admin, "a1": a1, "a2": a2, "lead": lead, "contact": contact,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_a1": {"Authorization": f"Bearer {create_access_token(a1.id)}"},
    }


@pytest.mark.asyncio
async def test_overview(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/overview", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["total"] == 6
    assert o["inbound"] == 2 and o["outbound"] == 4
    ch = {b["label"]: b["count"] for b in o["by_channel"]}
    assert ch == {"SMS": 2, "Call": 2, "Email": 1, "WhatsApp": 1}


@pytest.mark.asyncio
async def test_by_channel_rates_and_talk_time(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/by-channel", headers=data["h_admin"])
    rows = {c["channel"]: c for c in r.json()}
    assert rows["Call"]["avg_talk_time"] == 120
    assert rows["Email"]["opened"] == 1 and rows["Email"]["clicked"] == 1
    assert rows["WhatsApp"]["failed"] == 1


@pytest.mark.asyncio
async def test_agent_performance(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/agents", headers=data["h_admin"])
    agents = {a["agent_name"]: a for a in r.json()}
    assert agents["Agent One"]["calls"] == 2
    assert agents["Agent One"]["avg_talk_time"] == 120
    assert agents["Agent One"]["avg_response_seconds"] == 300  # inbound→outbound SMS
    assert agents["Agent Two"]["total"] == 2


@pytest.mark.asyncio
async def test_response_and_talk_time(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/response-time", headers=data["h_admin"])
    assert r.json()["avg_response_seconds"] == 300 and r.json()["sample_size"] == 1
    r = await client.get("/api/v1/comm-analytics/talk-time", headers=data["h_admin"])
    assert r.json()["avg_talk_seconds"] == 120 and r.json()["total_talk_seconds"] == 120


@pytest.mark.asyncio
async def test_missed(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/missed", headers=data["h_admin"])
    m = r.json()
    assert m["missed_calls"] == 1
    assert m["failed_messages"] == 1  # failed whatsapp
    assert m["total_missed"] == 2


@pytest.mark.asyncio
async def test_conversion(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/conversion", headers=data["h_admin"])
    c = r.json()
    assert c["leads_contacted"] == 1  # only the one lead has comm activities
    assert c["converted"] == 1        # lead status = Won
    assert c["conversion_rate"] == 100.0
    assert c["revenue"] == 5000.0


@pytest.mark.asyncio
async def test_engagement(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/engagement", headers=data["h_admin"])
    rows = r.json()
    top = rows[0]
    assert top["entity_type"] == "lead"
    assert top["interactions"] == 4  # 2 SMS + 2 Calls on the lead
    assert set(top["channels"]) >= {"SMS", "Call"}


@pytest.mark.asyncio
async def test_heatmap(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/heatmap", headers=data["h_admin"])
    h = r.json()
    assert len(h["grid"]) == 7 and len(h["grid"][0]) == 24
    # all activities are Monday (weekday 0) in the 10:00 hour
    assert h["peak"]["weekday"] == 0 and h["peak"]["hour"] == 10
    assert h["total"] == 6


@pytest.mark.asyncio
async def test_filters(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/overview", params={"channel": "Call"}, headers=data["h_admin"])
    assert r.json()["total"] == 2
    r = await client.get("/api/v1/comm-analytics/overview", params={"direction": "INBOUND"}, headers=data["h_admin"])
    assert r.json()["total"] == 2
    r = await client.get("/api/v1/comm-analytics/overview", params={"agent_id": str(data["a2"].id)}, headers=data["h_admin"])
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_role_scoping(client: AsyncClient, setup: dict):
    data = setup
    # agent1 sees only own comms (4 of the 6)
    r = await client.get("/api/v1/comm-analytics/overview", headers=data["h_a1"])
    assert r.json()["total"] == 4


@pytest.mark.asyncio
async def test_csv_export(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/comm-analytics/export", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = [l for l in r.text.strip().splitlines() if l]
    assert lines[0].startswith("created_at,channel,direction")
    assert len(lines) == 7  # header + 6 rows

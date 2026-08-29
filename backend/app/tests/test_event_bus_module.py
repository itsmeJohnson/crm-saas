import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import PipelineStage
from app.models.event import Event, EventSubscription, EventDelivery
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Bus Org", "slug": "bus-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@bus.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@bus.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/events/catalog", headers=d["h_admin"])).json()
    assert "lead.converted" in cat["all_event_types"] and "payment.received" in cat["all_event_types"]
    assert "notification" in cat["families"] and "webhook" in cat["subscriber_types"]
    # employee cannot create subscriptions
    assert (await client.post("/api/v1/events/subscriptions", json={"name": "x", "config": {"url": "http://h"}}, headers=d["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_lead_create_publishes_event_and_workflow_subscriber_runs_once(client: AsyncClient, setup: dict, db: AsyncSession):
    """Backward compat: creating a lead publishes lead.created; the built-in
    workflow_engine subscriber runs (once) via the bus, and a published workflow
    still fires exactly once."""
    d = setup
    # a published workflow on lead_created that sets status
    graph = {"nodes": [{"id": "t1", "type": "trigger", "config": {"conditions": []}},
                       {"id": "a0", "type": "action", "config": {"action": "update_status", "value": "Contacted"}},
                       {"id": "end", "type": "end", "config": {}}],
             "edges": [{"from": "t1", "to": "a0"}, {"from": "a0", "to": "end"}]}
    wf = (await client.post("/api/v1/workflows", json={"name": "auto", "trigger_event": "lead_created", "graph": graph}, headers=d["h_admin"])).json()
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=d["h_admin"])

    lead = (await client.post("/api/v1/leads/", json={"last_name": "Ev", "title": "Deal"}, headers=d["h_admin"])).json()
    # workflow (via the bus subscriber) still mutated the lead — runs exactly once
    assert lead["status"] == "Contacted"
    # an Event was published for lead.created
    evs = (await db.execute(select(Event).filter(
        Event.organization_id == d["org"].id, Event.event_type == "lead.created"))).scalars().all()
    assert len(evs) == 1 and evs[0].source == "trigger"
    # the workflow_engine subscriber delivery was logged
    deliveries = (await db.execute(select(EventDelivery).filter(
        EventDelivery.event_id == evs[0].id, EventDelivery.subscriber == "workflow_engine"))).scalars().all()
    assert len(deliveries) == 1 and deliveries[0].status == "success"


@pytest.mark.asyncio
async def test_webhook_subscription_delivery_success(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    d = setup
    # stub httpx so the webhook "succeeds"
    class _Resp:
        status_code = 200
    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None): return _Resp()
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    sub = (await client.post("/api/v1/events/subscriptions", json={
        "name": "hook", "event_pattern": "lead.*", "subscriber_type": "webhook",
        "config": {"url": "http://example/hook"}, "max_attempts": 3}, headers=d["h_admin"])).json()
    assert sub["event_pattern"] == "lead.*"
    # publish a matching custom-ish event via lead creation
    await client.post("/api/v1/leads/", json={"last_name": "Hook", "title": "D"}, headers=d["h_admin"])
    # the webhook subscription got a successful delivery
    rows = (await db.execute(select(EventDelivery).filter(
        EventDelivery.subscription_id == uuid.UUID(sub["id"])))).scalars().all()
    assert len(rows) >= 1 and rows[0].status == "success" and rows[0].is_dead_letter is False


@pytest.mark.asyncio
async def test_webhook_retry_and_dead_letter_then_requeue(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    d = setup
    calls = {"n": 0}
    class _Resp:
        def __init__(self, code): self.status_code = code
    class _FailClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            calls["n"] += 1
            return _Resp(500)  # always fails
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _FailClient)

    sub = (await client.post("/api/v1/events/subscriptions", json={
        "name": "badhook", "event_pattern": "*", "subscriber_type": "webhook",
        "config": {"url": "http://example/bad"}, "max_attempts": 3}, headers=d["h_admin"])).json()
    # publish a custom event → webhook fails all 3 attempts → dead letter
    await client.post("/api/v1/events/publish", json={"name": "deal_won", "payload": {"a": 1}}, headers=d["h_admin"])
    assert calls["n"] == 3  # retried up to max_attempts
    dlq = (await client.get("/api/v1/events/dead-letter", headers=d["h_admin"])).json()
    assert len(dlq) == 1 and dlq[0]["is_dead_letter"] is True and dlq[0]["attempts"] == 3

    # now make the webhook succeed and requeue the dead letter
    class _OkClient(_FailClient):
        async def post(self, url, json=None): return _Resp(200)
    monkeypatch.setattr(httpx, "AsyncClient", _OkClient)
    rq = (await client.post(f"/api/v1/events/deliveries/{dlq[0]['id']}/requeue", headers=d["h_admin"])).json()
    assert rq["requeued"] is True and rq["delivered"] is True
    dlq2 = (await client.get("/api/v1/events/dead-letter", headers=d["h_admin"])).json()
    assert len(dlq2) == 0  # cleared


@pytest.mark.asyncio
async def test_custom_event_publish_and_execution_logs(client: AsyncClient, setup: dict):
    d = setup
    ev = (await client.post("/api/v1/events/publish", json={"name": "invoice_paid", "payload": {"amount": 99}}, headers=d["h_admin"])).json()
    assert ev["event_type"] == "custom.invoice_paid" and ev["source"] == "custom"
    # appears in the event log
    log = (await client.get("/api/v1/events/events", headers=d["h_admin"])).json()
    assert any(e["event_type"] == "custom.invoice_paid" for e in log)
    # deliveries endpoint works (no subscribers matched → empty)
    dels = (await client.get(f"/api/v1/events/events/{ev['id']}/deliveries", headers=d["h_admin"])).json()
    assert isinstance(dels, list)


@pytest.mark.asyncio
async def test_subscription_pattern_matching(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    d = setup
    class _Resp: status_code = 200
    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None): return _Resp()
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    # only payment.* events
    sub = (await client.post("/api/v1/events/subscriptions", json={
        "name": "payments", "event_pattern": "payment.*", "subscriber_type": "webhook",
        "config": {"url": "http://e/p"}}, headers=d["h_admin"])).json()
    # publish a non-matching custom event → no delivery to this sub
    await client.post("/api/v1/events/publish", json={"name": "unrelated"}, headers=d["h_admin"])
    rows = (await db.execute(select(EventDelivery).filter(
        EventDelivery.subscription_id == uuid.UUID(sub["id"])))).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_monitoring_stats_and_dashboard(client: AsyncClient, setup: dict):
    d = setup
    await client.post("/api/v1/events/publish", json={"name": "a"}, headers=d["h_admin"])
    await client.post("/api/v1/events/publish", json={"name": "b"}, headers=d["h_admin"])
    stats = (await client.get("/api/v1/events/stats", headers=d["h_admin"])).json()
    assert stats["total_events"] >= 2 and "by_type" in stats and "success_rate" in stats
    dash = (await client.get("/api/v1/events/dashboard", headers=d["h_admin"])).json()
    assert dash["total_events"] >= 2 and "recent" in dash and "dead_letter" in dash

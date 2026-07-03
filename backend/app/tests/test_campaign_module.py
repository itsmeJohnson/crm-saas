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
from app.models.campaign import Campaign, CampaignRecipient
from app.models.notification import Notification
from app.models.workflow_rule import WorkflowRule
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
        return ["CAMPAIGN_MANAGEMENT", "SMS_MESSAGING", "EMAIL_MESSAGING", "WHATSAPP_MESSAGING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Camp Org", "slug": "camp-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@camp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@camp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()

    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()

    # 3 leads with phone+email, 1 without contact info
    leads = []
    for i in range(3):
        leads.append(Lead(organization_id=org.id, first_name=f"L{i}", last_name="Ead", email=f"l{i}@buyer.com",
                          phone=f"+91900000000{i}", title=f"Lead {i}", status="New", source="Web",
                          assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id, value=1000))
    noinfo = Lead(organization_id=org.id, first_name="No", last_name="Info", title="No contact", status="New",
                  source="Web", created_by=admin.id, stage_id=stage.id)
    db.add_all(leads + [noinfo])
    await db.commit()

    return {
        "org": org, "admin": admin, "emp": emp, "leads": leads, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _mk(client, headers, **over):
    payload = {"name": "Promo", "channel": "SMS", "body": "Hi {{first_name}}",
               "audience_type": "filter", "entity_type": "lead",
               "audience_definition": {"status": "New"}, "cost_per_message": 0.5}
    payload.update(over)
    return await client.post("/api/v1/campaigns", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_create_and_audience_preview(client: AsyncClient, setup: dict):
    data = setup
    r = await _mk(client, data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "draft"

    # preview counts only leads reachable on SMS (3 with phone, not the no-info lead)
    r = await client.post("/api/v1/campaigns/audience/preview", json={
        "channel": "SMS", "entity_type": "lead", "audience_type": "filter",
        "audience_definition": {"status": "New"}}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["count"] == 3


@pytest.mark.asyncio
async def test_invalid_channel_and_missing_body(client: AsyncClient, setup: dict):
    data = setup
    assert (await _mk(client, data["h_admin"], channel="Pigeon")).status_code == 400
    # message channel without template or body → 400
    assert (await _mk(client, data["h_admin"], body=None, template_id=None)).status_code == 400


@pytest.mark.asyncio
async def test_build_and_launch_sms_processes_queue(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    cid = (await _mk(client, data["h_admin"])).json()["id"]
    r = await client.post(f"/api/v1/campaigns/{cid}/build", json={}, headers=data["h_admin"])
    assert r.json()["total_recipients"] == 3

    # employee cannot launch
    assert (await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_emp"])).status_code == 403

    r = await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"  # mock provider sends all synchronously
    assert body["sent_count"] == 3

    # recipients now sent, each linked to an SMS activity
    recs = list((await db.execute(select(CampaignRecipient).filter(CampaignRecipient.campaign_id == uuid.UUID(cid)))).scalars().all())
    assert all(r.status in ("sent", "delivered") and r.activity_id for r in recs)
    acts = list((await db.execute(select(Activity).filter(Activity.activity_type == "SMS",
                Activity.organization_id == data["org"].id))).scalars().all())
    assert len(acts) == 3

    # creator notified on completion
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["admin"].id, Notification.category == "campaign"))).scalars().first()
    assert notif is not None


@pytest.mark.asyncio
async def test_email_campaign_reports_open_click_and_roi(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    cid = (await _mk(client, data["h_admin"], channel="Email", subject="Hi", body="Hello {{first_name}}",
                     cost_per_message=1.0)).json()["id"]
    await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_admin"])

    # simulate an open + click on the first recipient's email, and convert that lead
    recs = list((await db.execute(select(CampaignRecipient).filter(CampaignRecipient.campaign_id == uuid.UUID(cid)))).scalars().all())
    first = recs[0]
    act = (await db.execute(select(Activity).filter(Activity.id == first.activity_id))).scalars().first()
    act.email_open_count = 2
    act.email_click_count = 1
    db.add(act)
    lead = (await db.execute(select(Lead).filter(Lead.id == first.lead_id))).scalars().first()
    lead.status = "Won"  # converts, value=1000
    db.add(lead)
    await db.commit()

    r = await client.get(f"/api/v1/campaigns/{cid}/reports", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["sent"] == 3
    assert rep["opened"] == 1
    assert rep["clicked"] == 1
    assert rep["converted"] == 1
    assert rep["revenue"] == 1000.0
    assert rep["cost"] == 3.0            # 3 sent × 1.0
    assert rep["roi"] == 997.0           # 1000 − 3
    assert rep["conversion_rate"] == 33.3


@pytest.mark.asyncio
async def test_retry_failed(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    cid = (await _mk(client, data["h_admin"])).json()["id"]

    # force all sends to fail
    from app.services import campaign_service as mod
    from app.services.sms_providers import SmsSendResult

    class Failing:
        name = "mock"
        async def send(self, **kw): return SmsSendResult(status="failed", error="boom", segments=1)

    import app.services.sms_service as sms_mod
    monkeypatch.setattr(sms_mod, "get_provider", lambda s: Failing())

    await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_admin"])
    recs = list((await db.execute(select(CampaignRecipient).filter(CampaignRecipient.campaign_id == uuid.UUID(cid)))).scalars().all())
    assert all(r.status == "failed" for r in recs)

    # now let sends succeed and retry
    class Ok:
        name = "mock"
        async def send(self, **kw): return SmsSendResult(status="queued", provider_id="mock-x", segments=1)
    monkeypatch.setattr(sms_mod, "get_provider", lambda s: Ok())

    r = await client.post(f"/api/v1/campaigns/{cid}/retry", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    recs = list((await db.execute(select(CampaignRecipient).filter(CampaignRecipient.campaign_id == uuid.UUID(cid)))).scalars().all())
    assert all(r.status in ("sent", "delivered") and r.retry_count == 1 for r in recs)


@pytest.mark.asyncio
async def test_schedule_then_cron_runs(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    cid = (await _mk(client, data["h_admin"])).json()["id"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    r = await client.post(f"/api/v1/campaigns/{cid}/schedule", json={"scheduled_at": past}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
    assert r.json()["total_recipients"] == 3  # audience auto-built on schedule

    from app.services.campaign_service import process_scheduled_campaigns
    started = await process_scheduled_campaigns(db)
    await db.commit()
    assert started == 1
    c = (await db.execute(select(Campaign).filter(Campaign.id == uuid.UUID(cid)))).scalars().first()
    assert c.status == "completed"
    assert c.sent_count == 3


@pytest.mark.asyncio
async def test_call_campaign_is_queue_only(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    cid = (await _mk(client, data["h_admin"], channel="Call", body=None)).json()["id"]
    r = await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    # Call campaigns stay running (agents work the queue); no auto-send / no SMS activities
    assert r.json()["status"] == "running"
    recs = list((await db.execute(select(CampaignRecipient).filter(CampaignRecipient.campaign_id == uuid.UUID(cid)))).scalars().all())
    assert len(recs) == 3
    assert all(r.status == "pending" and r.activity_id is None for r in recs)


@pytest.mark.asyncio
async def test_pause_resume_cancel(client: AsyncClient, setup: dict):
    data = setup
    # Call campaign stays running so we can pause it
    cid = (await _mk(client, data["h_admin"], channel="Call", body=None)).json()["id"]
    await client.post(f"/api/v1/campaigns/{cid}/launch", headers=data["h_admin"])
    r = await client.post(f"/api/v1/campaigns/{cid}/pause", headers=data["h_admin"])
    assert r.json()["status"] == "paused"
    r = await client.post(f"/api/v1/campaigns/{cid}/resume", headers=data["h_admin"])
    assert r.json()["status"] == "running"
    r = await client.post(f"/api/v1/campaigns/{cid}/cancel", headers=data["h_admin"])
    assert r.json()["status"] == "cancelled"
    # cannot cancel twice
    assert (await client.post(f"/api/v1/campaigns/{cid}/cancel", headers=data["h_admin"])).status_code == 400


@pytest.mark.asyncio
async def test_segments_crud_and_use(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/campaigns/segments", json={
        "name": "New web leads", "entity_type": "lead", "definition": {"status": "New", "source": "Web"}},
        headers=data["h_admin"])
    assert r.status_code == 201, r.text
    seg_id = r.json()["id"]
    assert r.json()["cached_count"] == 4  # all 4 New/Web leads

    lst = await client.get("/api/v1/campaigns/segments", headers=data["h_admin"])
    assert any(s["id"] == seg_id for s in lst.json())

    # campaign using the segment resolves reachable SMS leads (3 with phone)
    cid = (await _mk(client, data["h_admin"], audience_type="segment", segment_id=seg_id,
                     audience_definition=None)).json()["id"]
    r = await client.post(f"/api/v1/campaigns/{cid}/build", json={}, headers=data["h_admin"])
    assert r.json()["total_recipients"] == 3

    assert (await client.delete(f"/api/v1/campaigns/segments/{seg_id}", headers=data["h_admin"])).status_code == 204


@pytest.mark.asyncio
async def test_workflow_add_to_campaign(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    cid = (await _mk(client, data["h_admin"])).json()["id"]
    # CRUD validation accepts the action
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Enrol", "trigger_event": "lead_created", "conditions": [],
        "actions": [{"type": "add_to_campaign", "campaign_id": cid}]}, headers=data["h_admin"])
    assert r.status_code == 201, r.text

    # run the action directly against a fresh lead
    from app.services.workflow_service import WorkflowService
    lead = Lead(organization_id=data["org"].id, first_name="Wf", last_name="Lead", email="wf@x.com",
                phone="+919999999999", title="WF", status="New", created_by=data["admin"].id,
                stage_id=data["stage"].id)
    db.add(lead)
    await db.commit()
    applied = await WorkflowService(db).run("lead_created", lead, data["admin"])
    await db.commit()
    assert "add_to_campaign" in applied
    rec = (await db.execute(select(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == uuid.UUID(cid), CampaignRecipient.lead_id == lead.id))).scalars().first()
    assert rec is not None


@pytest.mark.asyncio
async def test_dashboard_and_feature_gate(client: AsyncClient, setup: dict, monkeypatch):
    data = setup
    await _mk(client, data["h_admin"])
    r = await client.get("/api/v1/campaigns/dashboard", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["total"] == 1

    from app.dependencies import feature_guard

    async def no_feat(*a, **k):
        return ["LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", no_feat)
    assert (await _mk(client, data["h_admin"])).status_code == 403

import pytest
import uuid
from datetime import datetime, timezone
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
from app.models.notification import Notification
from app.models.sms_settings import SmsSettings
from app.models.workflow_rule import WorkflowRule
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key: str):
        return storage.get(key)

    async def mock_set(key: str, value: str, ex: int = 300):
        storage[key] = value
        return True

    async def mock_delete(key: str):
        storage.pop(key, None)
        return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_features(*args, **kwargs):
        return ["SMS_MESSAGING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "SMS Org", "slug": "sms-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@sms.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@sms.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@sms.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": manager.id})
    await db.commit()

    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage)
        await db.commit()

    lead = Lead(organization_id=org.id, first_name="Cust", last_name="Omer", phone="+919876500001",
                title="SMS Lead", status="New", assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id)
    contact = Contact(organization_id=org.id, first_name="Con", last_name="Tact", phone="+919876500002",
                      email="con@x.com", created_by=admin.id)
    db.add_all([lead, contact])
    await db.commit()

    return {
        "org": org, "admin": admin, "manager": manager, "emp": emp, "lead": lead, "contact": contact,
        "headers_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "headers_mgr": {"Authorization": f"Bearer {create_access_token(manager.id)}"},
        "headers_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


@pytest.mark.asyncio
async def test_settings_lazy_create_and_update_permissions(client: AsyncClient, setup: dict):
    data = setup
    # GET lazily creates a mock-provider row with a webhook token
    r = await client.get("/api/v1/sms/settings", headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock"
    assert body["webhook_token"]
    assert "auth_token" not in body  # write-only secret never returned

    # Employee cannot view or edit settings
    r = await client.get("/api/v1/sms/settings", headers=data["headers_emp"])
    assert r.status_code == 403
    r = await client.put("/api/v1/sms/settings", json={"daily_limit": 5}, headers=data["headers_emp"])
    assert r.status_code == 403

    # OrgAdmin can update + rotate token
    old_token = body["webhook_token"]
    r = await client.put("/api/v1/sms/settings", json={"sender_id": "CRMTXT", "daily_limit": 3,
                                                       "regenerate_webhook_token": True}, headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["sender_id"] == "CRMTXT"
    assert r.json()["daily_limit"] == 3
    assert r.json()["webhook_token"] != old_token


@pytest.mark.asyncio
async def test_send_single_via_mock_provider(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    r = await client.post("/api/v1/sms/send", json={"body": "Hello there", "lead_id": str(data["lead"].id)},
                          headers=data["headers_emp"])
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["direction"] == "OUTBOUND"
    assert item["sms_status"] == "queued"
    assert item["to_number"] == "+919876500001"  # derived from the lead phone
    assert item["segments"] == 1

    # persisted as an SMS Activity (feeds timeline/comm-center)
    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(item["id"])))).scalars().first()
    assert act.activity_type == "SMS"
    assert act.sms_provider_id.startswith("mock-")


@pytest.mark.asyncio
async def test_send_requires_number_and_feature(client: AsyncClient, setup: dict, monkeypatch):
    data = setup
    # no number and no linked entity → 400
    r = await client.post("/api/v1/sms/send", json={"body": "hi"}, headers=data["headers_admin"])
    assert r.status_code == 400

    # feature gate: disable SMS_MESSAGING
    from app.dependencies import feature_guard

    async def no_features(*args, **kwargs):
        return ["LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", no_features)
    r = await client.post("/api/v1/sms/send", json={"body": "hi", "to_number": "+911111111111"},
                          headers=data["headers_mgr"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_daily_cap_enforced(client: AsyncClient, setup: dict):
    data = setup
    await client.put("/api/v1/sms/settings", json={"daily_limit": 2}, headers=data["headers_admin"])
    for i in range(2):
        r = await client.post("/api/v1/sms/send", json={"body": f"m{i}", "to_number": "+9199999000%02d" % i},
                              headers=data["headers_admin"])
        assert r.status_code == 201, r.text
    r = await client.post("/api/v1/sms/send", json={"body": "over", "to_number": "+919999999999"},
                          headers=data["headers_admin"])
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_bulk_send(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/sms/send-bulk", json={
        "body": "Promo blast",
        "recipients": [
            {"to_number": "+911234500001"},
            {"lead_id": str(data["lead"].id)},
            {"contact_id": str(data["contact"].id)},
        ],
    }, headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert body["queued"] == 3
    assert body["failed"] == 0
    assert len(body["activity_ids"]) == 3


@pytest.mark.asyncio
async def test_status_webhook_updates_delivery(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    send = await client.post("/api/v1/sms/send", json={"body": "track me", "to_number": "+911234500009"},
                             headers=data["headers_admin"])
    aid = send.json()["id"]
    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(aid)))).scalars().first()
    provider_id = act.sms_provider_id
    token = (await db.execute(select(SmsSettings).filter(
        SmsSettings.organization_id == data["org"].id))).scalars().first().webhook_token

    # bad token rejected
    r = await client.post("/api/v1/sms/webhook/status", json={
        "token": "wrong", "provider_message_id": provider_id, "status": "delivered"})
    assert r.status_code == 401

    r = await client.post("/api/v1/sms/webhook/status", json={
        "token": token, "provider_message_id": provider_id, "status": "delivered"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "updated"

    await db.refresh(act)
    assert act.sms_status == "delivered"


@pytest.mark.asyncio
async def test_inbound_webhook_matches_notifies_and_triggers(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    token = (await db.execute(select(SmsSettings).filter(
        SmsSettings.organization_id == data["org"].id))).scalars().first()
    if not token:
        # ensure settings exist
        await client.get("/api/v1/sms/settings", headers=data["headers_admin"])
        token = (await db.execute(select(SmsSettings).filter(
            SmsSettings.organization_id == data["org"].id))).scalars().first()
    wtoken = token.webhook_token

    # workflow rule on sms_received
    db.add(WorkflowRule(organization_id=data["org"].id, name="SMS auto-priority", trigger_event="sms_received",
                        is_active=True, conditions=[], actions=[{"type": "set_priority", "value": "Urgent"}],
                        created_by=data["admin"].id))
    await db.commit()

    # bad token rejected
    r = await client.post("/api/v1/sms/webhook/inbound", json={
        "token": "nope", "from_number": "+919876500001", "body": "hi"})
    assert r.status_code == 401

    r = await client.post("/api/v1/sms/webhook/inbound", json={
        "token": wtoken, "from_number": "+919876500001", "to_number": "CRMTXT", "body": "Interested!"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "received"
    assert body["lead_id"] == str(data["lead"].id)

    # inbound SMS activity created
    inbound = (await db.execute(select(Activity).filter(
        Activity.organization_id == data["org"].id, Activity.activity_type == "SMS",
        Activity.call_direction == "INBOUND"))).scalars().first()
    assert inbound is not None
    assert inbound.sms_status == "received"

    # owner notified
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.category == "sms"))).scalars().first()
    assert notif is not None

    # workflow fired
    await db.refresh(data["lead"])
    assert data["lead"].priority == "Urgent"


@pytest.mark.asyncio
async def test_retry_failed_message(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    # Force the provider to fail the first send
    from app.services import sms_service as sms_mod
    from app.services.sms_providers import SmsSendResult

    class FailingProvider:
        name = "mock"
        async def send(self, **kwargs):
            return SmsSendResult(status="failed", error="boom", segments=1)

    monkeypatch.setattr(sms_mod, "get_provider", lambda s: FailingProvider())
    send = await client.post("/api/v1/sms/send", json={"body": "will fail", "to_number": "+911234500011"},
                             headers=data["headers_admin"])
    assert send.status_code == 201
    aid = send.json()["id"]
    assert send.json()["sms_status"] == "failed"

    # Now let the provider succeed and retry
    class OkProvider:
        name = "mock"
        async def send(self, **kwargs):
            return SmsSendResult(status="queued", provider_id="mock-retry", segments=1)

    monkeypatch.setattr(sms_mod, "get_provider", lambda s: OkProvider())
    r = await client.post(f"/api/v1/sms/{aid}/retry", headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["sms_status"] == "queued"
    assert r.json()["retry_count"] == 1


@pytest.mark.asyncio
async def test_messages_history_and_reports(client: AsyncClient, setup: dict):
    data = setup
    await client.post("/api/v1/sms/send", json={"body": "a", "to_number": "+911234500021"}, headers=data["headers_admin"])
    await client.post("/api/v1/sms/send", json={"body": "b", "lead_id": str(data["lead"].id)}, headers=data["headers_emp"])

    # admin sees both; employee sees only own
    r = await client.get("/api/v1/sms/messages", headers=data["headers_admin"])
    assert r.json()["total"] == 2
    r = await client.get("/api/v1/sms/messages", headers=data["headers_emp"])
    assert r.json()["total"] == 1

    # direction filter
    r = await client.get("/api/v1/sms/messages", params={"direction": "OUTBOUND"}, headers=data["headers_admin"])
    assert r.json()["total"] == 2

    # reports
    r = await client.get("/api/v1/sms/reports", headers=data["headers_admin"])
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["total"] == 2
    assert rep["outbound"] == 2
    assert rep["segments"] >= 2
    dirs = {b["label"]: b["count"] for b in rep["by_direction"]}
    assert dirs.get("OUTBOUND") == 2


@pytest.mark.asyncio
async def test_workflow_crud_accepts_sms_trigger_and_action(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "SMS on inbound", "trigger_event": "sms_received",
        "conditions": [], "actions": [{"type": "send_sms", "message": "Thanks for your message!"}]},
        headers=data["headers_admin"])
    assert r.status_code == 201, r.text

    r = await client.post("/api/v1/leads/workflows", json={
        "name": "bad", "trigger_event": "sms_delivered", "conditions": [], "actions": []},
        headers=data["headers_admin"])
    assert r.status_code == 400

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
from app.models.notification import Notification
from app.models.whatsapp import WhatsAppSettings, WhatsAppConversation
from app.models.communication import CommunicationTemplate
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
        return ["WHATSAPP_MESSAGING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "WA Org", "slug": "wa-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@wa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@wa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@wa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": manager.id})
    await db.commit()

    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage)
        await db.commit()

    lead = Lead(organization_id=org.id, first_name="Cust", last_name="Omer", phone="+919876511001",
                title="WA Lead", status="New", assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id)
    db.add(lead)
    await db.commit()

    return {
        "org": org, "admin": admin, "manager": manager, "emp": emp, "lead": lead,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(manager.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _settings(db, org_id) -> WhatsAppSettings:
    return (await db.execute(select(WhatsAppSettings).filter(
        WhatsAppSettings.organization_id == org_id))).scalars().first()


async def _open_window(db, org_id, phone):
    """Simulate an inbound so the 24h window is open for that phone."""
    settings = (await db.execute(select(WhatsAppSettings).filter(
        WhatsAppSettings.organization_id == org_id))).scalars().first()
    if not settings:
        settings = WhatsAppSettings(
            organization_id=org_id, provider="mock",
            webhook_token="token", webhook_verify_token="verify"
        )
        db.add(settings)
        await db.commit()
    conv = (await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.organization_id == org_id, WhatsAppConversation.phone == phone,
        WhatsAppConversation.whatsapp_settings_id == settings.id))).scalars().first()
    if not conv:
        conv = WhatsAppConversation(organization_id=org_id, phone=phone, whatsapp_settings_id=settings.id)
        db.add(conv)
    conv.last_inbound_at = datetime.now(timezone.utc)
    conv.window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db.add(conv)
    await db.commit()
    return conv


@pytest.mark.asyncio
async def test_settings_and_permissions(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/whatsapp/settings", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock"
    assert body["webhook_token"] and body["webhook_verify_token"]
    assert "access_token" not in body

    # employee cannot view/update
    assert (await client.get("/api/v1/whatsapp/settings", headers=data["h_emp"])).status_code == 403
    assert (await client.put("/api/v1/whatsapp/settings", json={"daily_limit": 5}, headers=data["h_emp"])).status_code == 403

    r = await client.put("/api/v1/whatsapp/settings", json={
        "sender_number": "+1555", "auto_reply_enabled": True, "auto_reply_message": "Hi!",
        "regenerate_webhook_token": True}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["auto_reply_enabled"] is True
    assert r.json()["webhook_token"] != body["webhook_token"]


@pytest.mark.asyncio
async def test_24h_window_blocks_freeform_until_inbound(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/whatsapp/settings", headers=data["h_admin"])  # ensure settings exist

    # window closed → free-form text rejected with 409
    r = await client.post("/api/v1/whatsapp/send", json={"body": "hi", "to_number": "+919876511001"},
                          headers=data["h_admin"])
    assert r.status_code == 409, r.text

    # a template send is always allowed (business-initiated)
    r = await client.post("/api/v1/whatsapp/send-template", json={
        "template_name": "welcome", "to_number": "+919876511001"}, headers=data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["template_name"] == "welcome"

    # once the window is open, free-form text goes through
    await _open_window(db, data["org"].id, "+919876511001")
    r = await client.post("/api/v1/whatsapp/send", json={"body": "now allowed", "to_number": "+919876511001"},
                          headers=data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["wa_status"] == "sent"
    assert r.json()["direction"] == "OUTBOUND"


@pytest.mark.asyncio
async def test_template_from_stored_template(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    t = CommunicationTemplate(organization_id=data["org"].id, name="promo", channel="WhatsApp",
                              body="Our promo!", created_by=data["admin"].id)
    db.add(t)
    await db.commit()
    r = await client.post("/api/v1/whatsapp/send-template", json={
        "template_id": str(t.id), "to_number": "+919876511009"}, headers=data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["template_name"] == "promo"


@pytest.mark.asyncio
async def test_status_webhook_read_receipt_ladder(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _open_window(db, data["org"].id, "+919876511002")
    send = await client.post("/api/v1/whatsapp/send", json={"body": "track", "to_number": "+919876511002"},
                             headers=data["h_admin"])
    aid = send.json()["id"]
    mid = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(aid)))).scalars().first().wa_message_id
    token = (await _settings(db, data["org"].id)).webhook_token

    assert (await client.post("/api/v1/whatsapp/webhook/status", json={
        "token": "bad", "message_id": mid, "status": "read"})).status_code == 401

    for st in ["delivered", "read"]:
        r = await client.post("/api/v1/whatsapp/webhook/status", json={
            "token": token, "message_id": mid, "status": st})
        assert r.status_code == 200, r.text
    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(aid)))).scalars().first()
    await db.refresh(act)
    assert act.wa_status == "read"

    # a late 'delivered' must not regress a 'read'
    r = await client.post("/api/v1/whatsapp/webhook/status", json={
        "token": token, "message_id": mid, "status": "delivered"})
    assert r.json()["status"] == "stale"
    await db.refresh(act)
    assert act.wa_status == "read"


@pytest.mark.asyncio
async def test_webhook_verify_handshake(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/whatsapp/settings", headers=data["h_admin"])
    verify = (await _settings(db, data["org"].id)).webhook_verify_token

    r = await client.get("/api/v1/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": verify, "hub.challenge": "12345"})
    assert r.status_code == 200
    assert r.text == "12345"

    r = await client.get("/api/v1/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_inbound_matches_notifies_autoreply_and_workflow(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.put("/api/v1/whatsapp/settings", json={
        "auto_reply_enabled": True, "auto_reply_message": "Thanks, we'll reply soon."}, headers=data["h_admin"])
    token = (await _settings(db, data["org"].id)).webhook_token

    db.add(WorkflowRule(organization_id=data["org"].id, name="WA priority", trigger_event="whatsapp_received",
                        is_active=True, conditions=[], actions=[{"type": "set_priority", "value": "Urgent"}],
                        created_by=data["admin"].id))
    await db.commit()

    assert (await client.post("/api/v1/whatsapp/webhook/inbound", json={
        "token": "bad", "from_number": "+919876511001", "body": "hi"})).status_code == 401

    r = await client.post("/api/v1/whatsapp/webhook/inbound", json={
        "token": token, "from_number": "+919876511001", "body": "I need help", "message_id": "wamid.in1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "received"
    assert body["lead_id"] == str(data["lead"].id)
    assert body["auto_reply_sent"] is True

    conv = (await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.organization_id == data["org"].id))).scalars().first()
    assert conv.assigned_user_id == data["emp"].id  # auto-assigned to lead owner
    assert conv.unread_count == 1
    assert conv.window_expires_at is not None

    # inbound + auto-reply outbound both recorded
    msgs = (await db.execute(select(Activity).filter(
        Activity.wa_conversation_id == conv.id).order_by(Activity.created_at.asc()))).scalars().all()
    assert any(m.call_direction == "INBOUND" for m in msgs)
    assert any(m.call_direction == "OUTBOUND" and m.description == "Thanks, we'll reply soon." for m in msgs)

    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.category == "whatsapp"))).scalars().first()
    assert notif is not None

    await db.refresh(data["lead"])
    assert data["lead"].priority == "Urgent"


@pytest.mark.asyncio
async def test_conversations_scoping_thread_and_assignment(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    token = (await client.get("/api/v1/whatsapp/settings", headers=data["h_admin"])).json()["webhook_token"]
    # unassigned inbound (no matching lead/contact)
    await client.post("/api/v1/whatsapp/webhook/inbound", json={
        "token": token, "from_number": "+919999000111", "body": "hello", "message_id": "wamid.u1"})
    # matched inbound → assigned to emp
    await client.post("/api/v1/whatsapp/webhook/inbound", json={
        "token": token, "from_number": "+919876511001", "body": "hi there", "message_id": "wamid.u2"})

    # admin sees both conversations
    r = await client.get("/api/v1/whatsapp/conversations", headers=data["h_admin"])
    assert len(r.json()) == 2
    # employee sees only the one assigned to them
    r = await client.get("/api/v1/whatsapp/conversations", headers=data["h_emp"])
    assert len(r.json()) == 1
    assert r.json()[0]["assigned_user_id"] == str(data["emp"].id)
    assert r.json()[0]["unread_count"] == 1

    conv_id = r.json()[0]["id"]
    # thread marks read
    thr = await client.get(f"/api/v1/whatsapp/conversations/{conv_id}", headers=data["h_emp"])
    assert thr.status_code == 200
    assert len(thr.json()["messages"]) >= 1
    again = await client.get("/api/v1/whatsapp/conversations", headers=data["h_emp"])
    assert again.json()[0]["unread_count"] == 0

    # employee cannot assign; manager can
    assert (await client.post(f"/api/v1/whatsapp/conversations/{conv_id}/assign",
            json={"user_id": str(data["manager"].id)}, headers=data["h_emp"])).status_code == 403
    r = await client.post(f"/api/v1/whatsapp/conversations/{conv_id}/assign",
                          json={"user_id": str(data["manager"].id)}, headers=data["h_mgr"])
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] == str(data["manager"].id)


@pytest.mark.asyncio
async def test_quick_replies_crud(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/whatsapp/quick-replies", json={"shortcut": "hi", "text": "Hello, how can I help?"},
                          headers=data["h_emp"])
    assert r.status_code == 201, r.text
    qr_id = r.json()["id"]
    r = await client.get("/api/v1/whatsapp/quick-replies", headers=data["h_emp"])
    assert any(q["shortcut"] == "hi" for q in r.json())
    assert (await client.delete(f"/api/v1/whatsapp/quick-replies/{qr_id}", headers=data["h_emp"])).status_code == 204
    r = await client.get("/api/v1/whatsapp/quick-replies", headers=data["h_emp"])
    assert not any(q["id"] == qr_id for q in r.json())


@pytest.mark.asyncio
async def test_reports(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    token = (await client.get("/api/v1/whatsapp/settings", headers=data["h_admin"])).json()["webhook_token"]
    await _open_window(db, data["org"].id, "+919876511001")
    send = await client.post("/api/v1/whatsapp/send", json={"body": "outbound", "to_number": "+919876511001"},
                             headers=data["h_admin"])
    mid = (await db.execute(select(Activity).filter(
        Activity.id == uuid.UUID(send.json()["id"])))).scalars().first().wa_message_id
    await client.post("/api/v1/whatsapp/webhook/status", json={"token": token, "message_id": mid, "status": "read"})
    await client.post("/api/v1/whatsapp/webhook/inbound", json={
        "token": token, "from_number": "+919876511001", "body": "reply", "message_id": "wamid.r1"})

    r = await client.get("/api/v1/whatsapp/reports", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["outbound"] >= 1
    assert rep["inbound"] >= 1
    assert rep["read"] >= 1
    assert rep["read_rate"] > 0


@pytest.mark.asyncio
async def test_workflow_crud_accepts_wa_trigger_and_action(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "WA reply", "trigger_event": "whatsapp_received",
        "conditions": [], "actions": [{"type": "send_whatsapp", "message": "Thanks!"}]},
        headers=data["h_admin"])
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "bad", "trigger_event": "whatsapp_delivered", "conditions": [], "actions": []},
        headers=data["h_admin"])
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rotate_token(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()
    
    from app.services.whatsapp_providers import MetaWhatsAppProvider
    async def mock_health(*args, **kwargs):
        return "connected"
    monkeypatch.setattr(MetaWhatsAppProvider, "check_health", mock_health)
    
    r = await client.post(f"/api/v1/whatsapp/settings/{s.id}/rotate-token", json={"access_token": "new_permanent_token"}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["health_status"] == "connected"


@pytest.mark.asyncio
async def test_set_default_settings(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()
    
    r = await client.post(f"/api/v1/whatsapp/settings/{s.id}/set-default", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["is_default"] is True


@pytest.mark.asyncio
async def test_exchange_signup_oauth(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()
    
    from app.services.whatsapp_providers import MetaWhatsAppProvider
    async def mock_exchange(*args, **kwargs):
        return "mocked_user_token"
    async def mock_wabas(*args, **kwargs):
        return [{"id": "waba_12345", "name": "Test WABA"}]
    async def mock_phones(*args, **kwargs):
        return [{
            "id": "phone_12345",
            "display_phone_number": "+1555010001",
            "verified_name": "Test Phone",
            "quality_rating": "GREEN",
            "messaging_limit_tier": "TIER_1K",
            "display_name_status": "APPROVED"
        }]
        
    monkeypatch.setattr(MetaWhatsAppProvider, "exchange_auth_code", mock_exchange)
    monkeypatch.setattr(MetaWhatsAppProvider, "fetch_shared_wabas", mock_wabas)
    monkeypatch.setattr(MetaWhatsAppProvider, "fetch_waba_phone_numbers", mock_phones)
    
    r = await client.post("/api/v1/whatsapp/signup/exchange", json={"code": "auth_code_from_facebook", "redirect_uri": "http://localhost:3000/callback"}, headers=data["h_admin"])
    assert r.status_code == 200
    res = r.json()
    assert len(res) == 1
    assert res[0]["phone_number_id"] == "phone_12345"
    assert res[0]["business_account_id"] == "waba_12345"
    assert res[0]["sender_number"] == "+1555010001"


@pytest.mark.asyncio
async def test_raw_body_signature_verification(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()
    
    from app.core.crypto import encrypt
    s.webhook_secret_enc = encrypt("my_super_secret")
    db.add(s)
    await db.commit()
    
    import hmac
    import hashlib
    import json
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "+1555010001", "phone_number_id": "phone_12345"},
                            "statuses": [
                                {
                                    "id": "wamid.ID1",
                                    "status": "delivered",
                                    "timestamp": "1672531199",
                                    "recipient_id": "+919876511001"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    sig = "sha256=" + hmac.new(b"my_super_secret", raw_body, hashlib.sha256).hexdigest()
    
    r = await client.post("/api/v1/whatsapp/webhooks", content=raw_body, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200
    
    r_bad = await client.post("/api/v1/whatsapp/webhooks", content=raw_body, headers={"X-Hub-Signature-256": "sha256=invalidhash"})
    assert r_bad.status_code == 401


@pytest.mark.asyncio
async def test_monitoring_dashboard(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()
    
    r = await client.get("/api/v1/whatsapp/monitoring/dashboard", headers=data["h_admin"])
    assert r.status_code == 200
    res = r.json()
    assert "connected_accounts" in res
    assert "quality_ratings" in res
    assert "messaging_limits" in res
    assert "webhook_status" in res


@pytest.mark.asyncio
async def test_delete_whatsapp_settings(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_delete_123", webhook_token="token", webhook_verify_token="verify",
        is_default=True
    )
    db.add(s)
    await db.commit()

    r = await client.delete(f"/api/v1/whatsapp/settings/{s.id}", headers=data["h_admin"])
    assert r.status_code == 204

    # Check that settings is soft deleted
    await db.refresh(s)
    assert s.is_deleted is True


@pytest.mark.asyncio
async def test_whatsapp_manual_refresh(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    from app.core.crypto import encrypt
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", business_account_id="waba_12345",
        access_token=encrypt("EAAG_mock_ref"), webhook_token="token", webhook_verify_token="verify"
    )
    db.add(s)
    await db.commit()

    r = await client.post(f"/api/v1/whatsapp/settings/{s.id}/refresh", headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["status"] == "success"


@pytest.mark.asyncio
async def test_whatsapp_diagnostics(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    s = WhatsAppSettings(
        organization_id=data["org"].id, provider="meta",
        phone_number_id="phone_12345", webhook_token="token", webhook_verify_token="verify",
        webhook_url="https://localhost:8000/webhook"
    )
    db.add(s)
    await db.commit()

    r = await client.get(f"/api/v1/whatsapp/settings/{s.id}/diagnostics", headers=data["h_admin"])
    assert r.status_code == 200
    res = r.json()
    assert res["webhook_reachable"] == "green"
    assert "token_valid" in res
    assert "phone_verified" in res
    assert "graph_api_reachable" in res
    assert "template_sync" in res


@pytest.mark.asyncio
async def test_whatsapp_hourly_sync_cron(db: AsyncSession):
    from app.cron.whatsapp_cron import run_whatsapp_hourly_sync
    from app.core.crypto import encrypt
    s = WhatsAppSettings(
        organization_id=uuid.uuid4(), provider="meta",
        phone_number_id="phone_cron_test", business_account_id="waba_cron",
        access_token=encrypt("EAAG_mock_cron"), webhook_token="token", webhook_verify_token="verify",
        is_active=True
    )
    db.add(s)
    await db.commit()

    # Stub session maker
    class MockSession:
        def __init__(self, db_session):
            self.db = db_session
        async def __aenter__(self):
            return self.db
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_session_maker():
        return MockSession(db)

    # This should complete without exceptions
    await run_whatsapp_hourly_sync(mock_session_maker)

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
from app.models.pipeline import Pipeline, PipelineStage
from app.models.whatsapp import WhatsAppSettings, WhatsAppConversation, WhatsAppMessage
from app.services.whatsapp_providers import GupshupWhatsAppProvider, get_provider
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
    org = await org_repo.create({"name": "Telecalling Agency Org", "slug": "telecalling-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@telecalling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Agency", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    await db.commit()

    caller = await user_repo.create_user(org.id, {
        "email": "caller1@telecalling.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ravi", "last_name": "Kumar", "role": "Employee", "is_active": True})
    await db.commit()

    pipeline = Pipeline(organization_id=org.id, name="Sales", is_default=True)
    db.add(pipeline)
    await db.flush()

    stage = PipelineStage(organization_id=org.id, pipeline_id=pipeline.id, name="New", order_position=1, is_system_default=True)
    db.add(stage)
    await db.commit()

    return {
        "org_id": org.id,
        "admin_id": admin.id,
        "caller_id": caller.id,
        "stage_id": stage.id,
        "token_admin": create_access_token(admin.id),
        "token_caller": create_access_token(caller.id),
    }


@pytest.mark.asyncio
async def test_gupshup_provider_methods():
    provider = GupshupWhatsAppProvider(
        app_name="TelecallingCRM",
        api_key="mock_access_token",
        sender_number="919876543210"
    )
    assert provider.name == "gupshup"
    assert provider.supports_templates is True

    # Test send_text
    res = await provider.send_text(to_number="+919811122233", body="Hello from Telecalling Agency!")
    assert res.status == "sent"
    assert res.message_id is not None

    # Test send_template
    res_tmpl = await provider.send_template(
        to_number="919811122233",
        template_name="call_followup_lead",
        language="en",
        variables=["Amit", "Health Insurance Policy"]
    )
    assert res_tmpl.status == "sent"

    # Test send_media
    res_media = await provider.send_media(
        to_number="919811122233",
        media_url="https://example.com/brochure.pdf",
        media_type="document",
        file_name="brochure.pdf"
    )
    assert res_media.status == "sent"

    # Test template sync
    templates = await provider.sync_templates()
    template_names = [t["name"] for t in templates]
    assert "hiring" in template_names

    # Test health check
    health = await provider.check_health()
    assert health == "connected"


@pytest.mark.asyncio
async def test_gupshup_crm_settings_and_webhook_flow(client: AsyncClient, setup: dict, db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup['token_admin']}"}

    # 1. Initialize & Configure Gupshup Settings via API
    init_res = await client.get("/api/v1/whatsapp/settings", headers=headers)
    assert init_res.status_code == 200, init_res.text
    initial_id = init_res.json()["id"]

    settings_res = await client.put("/api/v1/whatsapp/settings", json={
        "provider": "gupshup",
        "friendly_name": "Gupshup Agency Line",
        "business_account_id": "TelecallingApp",
        "phone_number_id": "TelecallingApp",
        "sender_number": "919876543210",
        "access_token": "mock_gupshup_api_key_12345",
        "is_active": True,
        "is_default": True
    }, headers=headers)
    assert settings_res.status_code == 200, settings_res.text
    s_data = settings_res.json()
    settings_id = s_data["id"]
    assert s_data["provider"] == "gupshup"
    assert s_data["sender_number"] == "919876543210"

    # 2. Test Gupshup Health Check endpoint
    health_res = await client.post(f"/api/v1/whatsapp/settings/{settings_id}/health", headers=headers)
    assert health_res.status_code == 200
    assert health_res.json()["health_status"] == "connected"

    # 3. Test Gupshup Template Sync
    sync_res = await client.post(f"/api/v1/whatsapp/settings/{settings_id}/sync-templates", headers=headers)
    assert sync_res.status_code == 200
    templates = sync_res.json()
    assert len(templates) > 0

    # 4. Create a Lead with customer phone
    customer_phone = "9899123456"
    lead = Lead(
        organization_id=setup["org_id"],
        first_name="Priya",
        last_name="Sharma",
        title="Priya Sharma",
        phone=f"+91{customer_phone}",
        status="New",
        assigned_user_id=setup["caller_id"],
        created_by=setup["admin_id"],
        stage_id=setup["stage_id"]
    )
    db.add(lead)
    await db.commit()

    # 5. Inbound Message Webhook from Gupshup
    now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    gupshup_inbound_payload = {
        "app": "TelecallingApp",
        "timestamp": now_ts,
        "version": 2,
        "type": "message",
        "payload": {
            "id": "gs_msg_998877",
            "source": f"91{customer_phone}",
            "type": "text",
            "payload": {
                "text": "Hi, I received a missed call. Please share details on WhatsApp."
            },
            "sender": {
                "phone": f"91{customer_phone}",
                "name": "Priya Sharma"
            }
        }
    }

    # Hit dedicated Gupshup webhook endpoint
    webhook_res = await client.post("/api/v1/whatsapp/webhook/gupshup", json=gupshup_inbound_payload)
    assert webhook_res.status_code == 200, webhook_res.text

    # Verify conversation created & linked to Priya Sharma's lead
    res_conv = await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.organization_id == setup["org_id"],
        WhatsAppConversation.phone == f"91{customer_phone}"
    ))
    conv = res_conv.scalars().first()
    assert conv is not None
    assert conv.lead_id == lead.id
    assert conv.assigned_user_id == setup["caller_id"]

    # Verify message persisted
    res_msg = await db.execute(select(WhatsAppMessage).filter(
        WhatsAppMessage.conversation_id == conv.id,
        WhatsAppMessage.wa_message_id == "gs_msg_998877"
    ))
    msg = res_msg.scalars().first()
    assert msg is not None
    assert "received a missed call" in msg.body
    assert msg.direction == "INBOUND"

    # 6. Test Outbound Message Dispatch via Gupshup
    send_res = await client.post("/api/v1/whatsapp/send-text", json={
        "conversation_id": str(conv.id),
        "body": "Hello Priya, here is our product brochure."
    }, headers={"Authorization": f"Bearer {setup['token_caller']}"})
    assert send_res.status_code == 201, send_res.text
    out_msg = send_res.json()
    assert out_msg["wa_status"] in ("sent", "delivered", "read", "queued")
    out_wamid = out_msg["wa_message_id"]

    # 7. Test Gupshup DLR / Status callback (message-event)
    gupshup_status_payload = {
        "app": "TelecallingApp",
        "timestamp": now_ts + 5000,
        "type": "message-event",
        "payload": {
            "id": out_wamid,
            "type": "delivered",
            "destination": f"91{customer_phone}",
            "ts": now_ts + 5000
        }
    }
    # Test via main /webhook endpoint (auto-delegation)
    status_res = await client.post("/api/v1/whatsapp/webhook", json=gupshup_status_payload)
    assert status_res.status_code == 200

    # Verify status updated
    await db.refresh(msg)
    res_out_msg = await db.execute(select(WhatsAppMessage).filter(
        WhatsAppMessage.wa_message_id == out_wamid
    ))
    updated_out = res_out_msg.scalars().first()
    assert updated_out is not None
    assert updated_out.wa_status in ("delivered", "read")

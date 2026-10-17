import pytest
from httpx import AsyncClient, Response
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.security import create_access_token, get_password_hash
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.telephony_settings import TelephonySettings
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.telephony_settings import TelephonyConfigUpdate
from app.services.telephony_config_service import TelephonyConfigService
from app.services.telephony.callerdesk import CallerdeskProvider
from app.services.telephony.factory import get_provider


@pytest.mark.asyncio
async def test_callerdesk_provider_start_call_success():
    cfg = {
        "provider": "callerdesk",
        "authcode": "test_auth_123",
        "deskphone": "08069241111",
    }
    provider = get_provider(cfg)
    assert isinstance(provider, CallerdeskProvider)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(
            200,
            json={
                "type": "success",
                "message": "Call to Customer Initiate Successfully..",
                "campid": 9876543,
                "callerid": "1204761111",
            }
        )

        res = await provider.start_call(number="+919620194983", agent_number="+919888776655")
        assert res["success"] is True
        assert res["call_id"] == "9876543"
        assert res["provider"] == "callerdesk"

        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]
        assert "click_to_call_v2" in called_url
        assert params["calling_party_a"] == "9888776655"
        assert params["calling_party_b"] == "9620194983"
        assert params["deskphone"] == "08069241111"
        assert params["authcode"] == "test_auth_123"
        assert params["call_from_did"] == "1"


@pytest.mark.asyncio
async def test_callerdesk_provider_connect_success():
    cfg = {
        "provider": "callerdesk",
        "authcode": "valid_token",
        "deskphone": "08069241111",
    }
    provider = CallerdeskProvider(cfg)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = Response(
            200,
            json={
                "login_account": {
                    "account_id": "1408847",
                    "company_name": "Samartha Sankalpa",
                    "call_coins": "5000",
                }
            }
        )
        res = await provider.connect()
        assert res["success"] is True
        assert "Samartha Sankalpa" in res["message"]


@pytest.mark.asyncio
async def test_callerdesk_inbound_and_outbound_webhooks(client: AsyncClient, db: AsyncSession):
    # Setup test org and user
    org = await OrganizationRepository(db).create({"name": "Callerdesk Org", "slug": "callerdesk-org"})
    await db.commit()

    user = await UserRepository(db).create_user(org.id, {
        "email": "agent@callerdesk.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Caller",
        "last_name": "Agent",
        "role": "SuperAdmin",
        "phone": "9888776655",
        "is_active": True,
    })
    await db.commit()

    # Pre-create lead
    from app.models.pipeline import Pipeline, PipelineStage
    pipeline = Pipeline(name="Default", organization_id=org.id)
    db.add(pipeline)
    await db.flush()
    stage = PipelineStage(name="New", organization_id=org.id, pipeline_id=pipeline.id, order_position=1)
    db.add(stage)
    await db.flush()

    lead = Lead(
        organization_id=org.id,
        first_name="Sunil",
        last_name="Customer",
        title="Prospective Client",
        phone="9620194983",
        status="New",
        stage_id=stage.id,
        created_by=user.id,
    )
    db.add(lead)
    await db.commit()

    # 1. Test Inbound Call Webhook (POST JSON)
    inbound_payload = {
        "type": "live_call",
        "SourceNumber": "09620194983",
        "DestinationNumber": "08069241111",
        "DialWhomNumber": "09888776655",
        "Status": "ANSWER",
        "CallSid": "call-inbound-999",
        "Direction": "IVR",
    }
    inbound_res = await client.post("/api/v1/telephony/webhook", json=inbound_payload)
    assert inbound_res.status_code == 200
    inbound_data = inbound_res.json()
    assert inbound_data["status"] == "matched"
    assert inbound_data["lead_id"] == str(lead.id)

    # Verify inbound Activity was recorded
    act_res = await db.execute(select(Activity).filter(Activity.call_sid == "call-inbound-999"))
    activity = act_res.scalars().first()
    assert activity is not None
    assert activity.call_direction == "INBOUND"
    assert activity.lead_id == lead.id

    # 2. Test Outbound Call Pre-created Activity & Call Report Webhook
    outbound_act = Activity(
        organization_id=org.id,
        activity_type="Call",
        subject="Outbound Call",
        status="Planned",
        assigned_user_id=user.id,
        lead_id=lead.id,
        created_by=user.id,
        call_sid="campid-12345",
        call_direction="OUTBOUND",
    )
    db.add(outbound_act)
    await db.commit()

    outbound_report_payload = {
        "type": "call_report",
        "campid": "campid-12345",
        "CallSid": "campid-12345",
        "SourceNumber": "09888776655",
        "DestinationNumber": "08069241111",
        "DialWhomNumber": "09620194983",
        "Status": "ANSWER",
        "CallDuration": "45",
        "TalkDuration": "40",
        "CallRecordingUrl": "https://callrecords.callerdesk.io/outgoing/rec_12345.wav",
        "Direction": "WEBOBD",
    }
    # Test on dedicated endpoint as well
    outbound_res = await client.post("/api/v1/telephony/callerdesk/webhook", json=outbound_report_payload)
    assert outbound_res.status_code == 200
    assert outbound_res.json()["status"] == "updated"

    # Verify activity was updated with recording and duration
    await db.refresh(outbound_act)
    assert outbound_act.status == "Completed"
    assert outbound_act.call_duration == 45
    assert outbound_act.recording_url == "https://callrecords.callerdesk.io/outgoing/rec_12345.wav"

    # 3. Test GET Webhook (Callerdesk query params format)
    get_res = await client.get(
        "/api/v1/telephony/webhook?SourceNumber=9620194983&DestinationNumber=08069241111&CallSid=get-call-777&Direction=IVR"
    )
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "matched"

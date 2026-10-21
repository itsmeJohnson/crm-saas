import pytest
import uuid
from app.services.telephony.factory import get_provider
from app.services.telephony.telecmi import TeleCMIProvider
from app.api.v1.dialer import config_ready


@pytest.mark.asyncio
async def test_telecmi_provider_factory():
    cfg = {
        "provider": "telecmi",
        "company_id": "33339071",
        "secret_token": "5c7597c2-a2f7-46fe-b0dc-ce7920639607",
        "default_caller_id": "917949817390",
    }
    provider = get_provider(cfg)
    assert isinstance(provider, TeleCMIProvider)
    assert provider.name == "telecmi"
    assert provider._get_appid() == 33339071
    assert provider._get_secret() == "5c7597c2-a2f7-46fe-b0dc-ce7920639607"
    assert provider._get_callerid() == 917949817390


def test_telecmi_config_ready():
    assert not config_ready(None)
    assert not config_ready({})
    assert not config_ready({"provider": "telecmi", "company_id": "33339071"})
    assert config_ready({
        "provider": "telecmi",
        "company_id": "33339071",
        "secret_token": "5c7597c2-a2f7-46fe-b0dc-ce7920639607",
        "default_caller_id": "917949817390",
    })


@pytest.mark.asyncio
async def test_telecmi_start_call_mock(monkeypatch):
    cfg = {
        "provider": "telecmi",
        "company_id": "33339071",
        "secret_token": "5c7597c2-a2f7-46fe-b0dc-ce7920639607",
        "default_caller_id": "917949817390",
    }
    provider = TeleCMIProvider(cfg)

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "code": 200,
                "msg": "Call initiated",
                "request_id": "test-cmi-uuid-12345",
            }

    async def mock_post(*args, **kwargs):
        assert kwargs["json"]["to"] == 919876543210
        assert kwargs["json"]["callerid"] == 917949817390
        assert kwargs["json"]["webrtc"] is True
        return MockResponse()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await provider.start_call(number="9876543210")
    assert result["success"] is True
    assert result["call_id"] == "test-cmi-uuid-12345"
    assert result["provider"] == "telecmi"


@pytest.mark.asyncio
async def test_telecmi_connect_mock(monkeypatch):
    cfg = {
        "provider": "telecmi",
        "company_id": "33339071",
        "secret_token": "5c7597c2-a2f7-46fe-b0dc-ce7920639607",
    }
    provider = TeleCMIProvider(cfg)

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "code": 200,
                "status": "success",
                "count": 1,
                "agents": [{"name": "Agent 1", "agent_id": "5001_33339071"}],
            }

    async def mock_post(*args, **kwargs):
        return MockResponse()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    conn_res = await provider.connect()
    assert conn_res["success"] is True
    assert "App ID: 33339071" in conn_res["message"]
    assert len(conn_res["agents"]) == 1

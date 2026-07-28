"""Dialer click-to-call dispatch over the org-level telephony config.

Pure unit tests — no DB/HTTP. The provider services are monkeypatched so these
assert routing + config-readiness only (a real OBD call is exercised against
MyOperator's sandbox, not here)."""
from app.api.v1 import dialer


def test_config_ready_is_provider_aware():
    # MyOperator needs company_id + x_api_key + secret_token + public_ivr_id.
    assert dialer.config_ready({
        "provider": "myoperator", "company_id": "c", "x_api_key": "k",
        "secret_token": "s", "public_ivr_id": "ivr"})
    assert not dialer.config_ready({
        "provider": "myoperator", "company_id": "c", "x_api_key": "k", "secret_token": "s"})  # no ivr
    # Knowlarity needs the org api key (agent phone comes from the user).
    assert dialer.config_ready({"provider": "knowlarity", "x_api_key": "k"})
    assert not dialer.config_ready({"provider": "knowlarity"})
    assert not dialer.config_ready(None)


def test_extract_call_id_handles_multiple_shapes():
    assert dialer._extract_call_id({"success": {"call_id": "ABC"}}, "fb") == "ABC"
    assert dialer._extract_call_id({"data": {"uid": "X9"}}, "fb") == "X9"
    assert dialer._extract_call_id({"request_id": "R1"}, "fb") == "R1"
    assert dialer._extract_call_id({}, "fb") == "fb"


async def test_dispatch_routes_to_myoperator(monkeypatch):
    seen = {}

    async def fake_myop(**kwargs):
        seen.update(kwargs)
        return {"success": {"call_id": "MOP123"}}

    monkeypatch.setattr("app.services.telephony.myoperator.trigger_myoperator_call", fake_myop)
    cfg = {"provider": "myoperator", "company_id": "c6a", "x_api_key": "k",
           "secret_token": "s", "public_ivr_id": "ivr9", "call_type": "2"}
    sid = await dialer.trigger_provider_call(cfg, "+9188", "+9199", "fallback")

    assert sid == "MOP123"
    assert seen["number"] == "+9188"
    assert seen["company_id"] == "c6a"
    assert seen["public_ivr_id"] == "ivr9"
    assert seen["call_type"] == "2"


async def test_dispatch_routes_to_knowlarity(monkeypatch):
    seen = {}

    async def fake_know(**kwargs):
        seen.update(kwargs)
        return {"call_id": "KNW9"}

    monkeypatch.setattr("app.services.telephony.knowlarity.trigger_knowlarity_call", fake_know)
    cfg = {"provider": "knowlarity", "x_api_key": "k", "default_caller_id": "srn1"}
    sid = await dialer.trigger_provider_call(cfg, "+9188", "+9111", "fallback")

    assert sid == "KNW9"
    assert seen["customer_number"] == "+9188"
    assert seen["agent_number"] == "+9111"  # per-user agent phone, not org-level

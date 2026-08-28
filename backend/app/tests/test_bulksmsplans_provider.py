"""Unit tests for the BulkSMSPlans SMS provider (seller.bulksmsplans.com).

The gateway speaks JSON `{code, message, data}` over POST/GET. These tests stub
httpx.AsyncClient so no network is hit, and assert how the provider builds each
request and parses each response (send, poll-based delivery report, balance,
sender-ID list). The vendor is poll-based — there is no delivery webhook — so the
delivery_report path is the one SmsService.poll_delivery_reports relies on.
"""
import pytest

from app.services import sms_providers as sp


class _JsonResponse:
    def __init__(self, status_code: int, payload, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    """Records the last POST/GET call and returns a canned response per-URL."""
    last_post: dict = {}
    last_get: dict = {}
    # url-substring -> response
    routes: dict = {}
    default: _JsonResponse = _JsonResponse(200, {"code": 200, "message": "ok", "data": {}})

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _resolve(self, url):
        for frag, resp in _FakeClient.routes.items():
            if frag in url:
                return resp
        return _FakeClient.default

    async def post(self, url, json=None, data=None, timeout=None):
        _FakeClient.last_post = {"url": url, "json": dict(json or {})}
        return self._resolve(url)

    async def get(self, url, params=None, timeout=None):
        _FakeClient.last_get = {"url": url, "params": dict(params or {})}
        return self._resolve(url)


@pytest.fixture(autouse=True)
def _stub_http(monkeypatch):
    _FakeClient.routes = {}
    monkeypatch.setattr(sp.httpx, "AsyncClient", _FakeClient)
    yield


# ── status mapping ────────────────────────────────────────────────────────────
def test_map_bulksms_status():
    assert sp.map_bulksms_status("Delivered") == "delivered"
    assert sp.map_bulksms_status("Rejected") == "failed"
    assert sp.map_bulksms_status("Blacklist Number") == "failed"   # substring match
    assert sp.map_bulksms_status("Pending") == "sent"
    assert sp.map_bulksms_status("DND") == "failed"
    assert sp.map_bulksms_status("") is None
    assert sp.map_bulksms_status("something new") is None


# ── provider resolution ───────────────────────────────────────────────────────
def test_get_provider_resolves_bulksmsplans():
    class S:
        is_active = True
        provider = "bulksmsplans"
        account_sid = "APIID"
        auth_token = "APIPW"
        sms_type = "Promotional"
        default_template_id = "12345"
    prov = sp.get_provider(S())
    assert isinstance(prov, sp.BulkSmsPlansProvider)
    assert prov.sms_type == "Promotional"
    assert prov.template_id == "12345"

    class S2(S):
        auth_token = None
    assert isinstance(sp.get_provider(S2()), sp.MockSmsProvider)


# ── send ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_success_parses_message_id_and_strips_country_code():
    _FakeClient.routes = {"/send_sms": _JsonResponse(
        200, {"code": 200, "message": "Message Submitted Successfully",
              "data": {"message_id": 198254, "number": "9620194983"}})}
    provider = sp.BulkSmsPlansProvider("APIID", "APIPW", sms_type="Transactional")
    res = await provider.send(to_number="+91 96201 94983", from_number="BLKSMS", body="Hello")
    assert res.status == "sent"
    assert res.provider_id == "198254"
    body = _FakeClient.last_post["json"]
    assert body["api_id"] == "APIID" and body["api_password"] == "APIPW"
    assert body["sender"] == "BLKSMS"
    assert body["number"] == "9620194983"          # 91 country code stripped
    assert body["sms_encoding"] == "1"             # ASCII -> text
    assert body["sms_type"] == "Transactional"
    assert "template_id" not in body               # none configured


@pytest.mark.asyncio
async def test_send_unicode_sets_encoding_2_and_template_id():
    _FakeClient.routes = {"/send_sms": _JsonResponse(
        200, {"code": 200, "data": {"message_id": 1}})}
    provider = sp.BulkSmsPlansProvider("id", "pw", template_id="TPL9")
    res = await provider.send(to_number="9620194983", from_number="BLKSMS", body="नमस्ते")
    assert res.status == "sent"
    body = _FakeClient.last_post["json"]
    assert body["sms_encoding"] == "2"             # non-ASCII -> unicode
    assert body["template_id"] == "TPL9"


@pytest.mark.asyncio
async def test_send_error_code_marks_failed():
    _FakeClient.routes = {"/send_sms": _JsonResponse(
        200, {"code": 108, "message": "Insufficient Balance"})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    res = await provider.send(to_number="9620194983", from_number="BLKSMS", body="Hi")
    assert res.status == "failed"
    assert "Insufficient Balance" in (res.error or "")


@pytest.mark.asyncio
async def test_send_missing_sender_fails_without_call():
    provider = sp.BulkSmsPlansProvider("id", "pw")
    res = await provider.send(to_number="9620194983", from_number="", body="Hi")
    assert res.status == "failed"
    assert "sender" in (res.error or "").lower()


# ── delivery report (poll-based DLR) ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_delivery_report_maps_status_and_error():
    _FakeClient.routes = {"/sms_delivery_report": _JsonResponse(
        200, {"code": 200, "message": "Get Message Successfully",
              "data": [{"message_id": 335960, "status": "Rejected",
                        "error_message": "Blacklist Number"}]})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    rep = await provider.delivery_report("335960")
    assert rep["found"] is True
    assert rep["status"] == "failed"
    assert rep["vendor_status"] == "Rejected"
    assert rep["error"] == "Blacklist Number"
    assert _FakeClient.last_get["params"]["message_id"] == "335960"


@pytest.mark.asyncio
async def test_delivery_report_no_rows_returns_not_found():
    _FakeClient.routes = {"/sms_delivery_report": _JsonResponse(
        200, {"code": 200, "data": []})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    rep = await provider.delivery_report("1")
    assert rep["found"] is False


# ── balance ───────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_check_balance_parses_amount_and_currency():
    _FakeClient.routes = {"/check_balance": _JsonResponse(
        200, {"code": 200, "data": [{"BalanceAmount": 2982.55, "CurrenceCode": "INR"}]})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    bal = await provider.check_balance()
    assert bal["success"] is True
    assert bal["amount"] == 2982.55
    assert bal["currency"] == "INR"


# ── sender IDs ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_sender_ids_unwraps_paginated_data():
    _FakeClient.routes = {"/get_sender_request_list": _JsonResponse(
        200, {"code": 200, "data": {"current_page": 1,
              "data": [{"sender_id": "TEST", "country": "India", "status": "Pending"}]}})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    out = await provider.list_sender_ids()
    assert out["success"] is True
    assert out["items"][0]["sender_id"] == "TEST"


# ── OTP verify / verify_status ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_otp_success_returns_message_id():
    _FakeClient.routes = {"/verify": _JsonResponse(
        200, {"code": 200, "message": "OTP Send Successfully", "data": {"message_id": 123456}})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    out = await provider.send_otp(number="9620194983", message="Code is {{otp}}", sender="BLKSMS")
    assert out["success"] is True and out["message_id"] == "123456"
    # /verify_status also contains "/verify" — assert the send hit the verify endpoint
    assert _FakeClient.last_post["url"].endswith("/verify")


@pytest.mark.asyncio
async def test_verify_otp_success_and_failure():
    _FakeClient.routes = {"/verify_status": _JsonResponse(
        200, {"code": 200, "message": "OTP Code is Verified"})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    ok = await provider.verify_otp(message_id="123456", otp="987654")
    assert ok["verified"] is True

    _FakeClient.routes = {"/verify_status": _JsonResponse(
        200, {"code": 108, "message": "Invalid OTP"})}
    bad = await provider.verify_otp(message_id="123456", otp="000000")
    assert bad["verified"] is False


@pytest.mark.asyncio
async def test_request_sender_id_success():
    _FakeClient.routes = {"/sender_request": _JsonResponse(
        200, {"code": 200, "message": "Get SenderID List Successfully"})}
    provider = sp.BulkSmsPlansProvider("id", "pw")
    out = await provider.request_sender_id("TEST", country="India", remarks="r")
    assert out["success"] is True
    body = _FakeClient.last_post["json"]
    assert body["sender"] == "TEST" and body["country"] == "India" and body["remarks"] == "r"

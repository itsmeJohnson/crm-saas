"""Unit tests for the BulkSMSPlans Voice/OBD provider.

Stubs httpx.AsyncClient (no network) and asserts request construction and
response parsing for TTS, OBD voice notes, media list/upload, and voice DLR.
"""
import pytest

from app.services import voice_providers as vp


class _JsonResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class _FakeClient:
    last_post = {}
    routes = {}
    default = _JsonResponse(200, {"code": 200, "data": {}})

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

    async def post(self, url, json=None, data=None, files=None, timeout=None):
        _FakeClient.last_post = {"url": url, "json": json, "data": data, "files": files}
        return self._resolve(url)


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    _FakeClient.routes = {}
    monkeypatch.setattr(vp.httpx, "AsyncClient", _FakeClient)
    yield


def test_map_voice_status_and_split_ids():
    assert vp.map_voice_status("Answered") == "answered"
    assert vp.map_voice_status("Busy") == "busy"
    assert vp.map_voice_status("No Answered") == "no_answer"
    assert vp.map_voice_status("DND") == "failed"
    assert vp.map_voice_status("") is None
    assert vp._split_ids('a,"b", c ') == ["a", "b", "c"]
    assert vp._split_ids(["x", "y"]) == ["x", "y"]
    assert vp._split_ids(None) == []


def test_build_voice_provider_only_for_bulksmsplans():
    class S:
        provider = "bulksmsplans"
        account_sid = "id"
        auth_token = "pw"
    assert isinstance(vp.build_voice_provider(S()), vp.BulkSmsPlansVoiceProvider)

    class Bhash(S):
        provider = "bhash"
    assert vp.build_voice_provider(Bhash()) is None

    class NoCreds(S):
        auth_token = None
    assert vp.build_voice_provider(NoCreds()) is None
    assert vp.build_voice_provider(None) is None


@pytest.mark.asyncio
async def test_send_tts_parses_job_and_unique_ids():
    _FakeClient.routes = {"/send_tts": _JsonResponse(
        200, {"code": 200, "data": {"status": 1, "job_id": 262073,
              "unique_ids": "674011f1e57c8,674012efc8ab9"}})}
    p = vp.BulkSmsPlansVoiceProvider("id", "pw")
    out = await p.send_tts(numbers=["9876543210", "9876543211"], content="Hi", language="Hindi", gender="Female")
    assert out["success"] is True
    assert out["job_id"] == 262073
    assert out["unique_ids"] == ["674011f1e57c8", "674012efc8ab9"]
    body = _FakeClient.last_post["json"]
    assert body["number"] == "9876543210,9876543211"
    assert body["language"] == "Hindi" and body["gender"] == "Female"


@pytest.mark.asyncio
async def test_send_voice_note_builds_scheduled_body():
    _FakeClient.routes = {"/send_voice_note": _JsonResponse(
        200, {"code": 200, "data": {"status": 1, "promotional": 0}})}
    p = vp.BulkSmsPlansVoiceProvider("id", "pw")
    out = await p.send_voice_note(numbers=["911234567890"], voice_type="33", voice_medias_id="123",
                                  scheduled=True, scheduled_datetime="2026-09-01 10:00:00",
                                  retry_interval=15, retry_count=2)
    assert out["success"] is True
    body = _FakeClient.last_post["json"]
    assert body["voice_type"] == "33" and body["voice_medias_id"] == "123"
    assert body["scheduled"] == "1" and body["scheduled_datetime"] == "2026-09-01 10:00:00"
    assert body["retry_interval"] == "15" and body["retry_count"] == "2"


@pytest.mark.asyncio
async def test_send_error_returns_message():
    _FakeClient.routes = {"/send_tts": _JsonResponse(200, {"code": 108, "message": "Insufficient Balance"})}
    p = vp.BulkSmsPlansVoiceProvider("id", "pw")
    out = await p.send_tts(numbers=["9876543210"], content="Hi")
    assert out["success"] is False
    assert "Insufficient Balance" in out["message"]


@pytest.mark.asyncio
async def test_fetch_report_and_upload_media():
    _FakeClient.routes = {
        "/voice/fetch_report": _JsonResponse(200, {"code": 200, "data": [
            {"unique_id": "u1", "number": "9876543210", "status": "Answered"}]}),
        "/add_voice_media": _JsonResponse(200, {"code": 200, "data": {
            "title": "t", "status": "Success", "announcement_id": 99, "file_seconds": 30, "type": "Promotional"}}),
    }
    p = vp.BulkSmsPlansVoiceProvider("id", "pw")
    rep = await p.fetch_report(["u1"])
    assert rep["success"] and rep["rows"][0]["status"] == "Answered"

    up = await p.add_voice_media(title="t", vendor_account_id="1", duration="0:30",
                                 file_bytes=b"xx", filename="a.mp3")
    assert up["success"] and up["announcement_id"] == 99
    assert _FakeClient.last_post["files"]["voice_note"][0] == "a.mp3"


@pytest.mark.asyncio
async def test_voice_dlr_report_unwraps_paginated():
    _FakeClient.routes = {"/VoiceDLRReport": _JsonResponse(200, {"code": 200, "data": {
        "current_page": 1, "data": [{"number": "9876543210", "status": "Busy"}], "total": 1}})}
    p = vp.BulkSmsPlansVoiceProvider("id", "pw")
    out = await p.voice_dlr_report(phone_number="9876543210")
    assert out["success"] and out["total"] == 1
    assert out["rows"][0]["status"] == "Busy"

"""BulkSMSPlans Voice / OBD provider (seller.bulksmsplans.com).

Bulk voice broadcast — distinct from the click-to-call telephony providers under
``app.services.telephony`` (which model a per-agent dialer). This handles
outbound voice blasts: pre-recorded voice notes (OBD) and text-to-speech (TTS)
to lists of numbers, plus voice delivery reports.

Credentials are the SAME BulkSMSPlans account as SMS, so the provider is built
from the org's :class:`SmsSettings` (api_id=account_sid, api_password=auth_token)
via :func:`build_voice_provider`. All methods return plain dicts and never raise
for a business/network failure — they return ``{"success": False, ...}`` so the
service can persist the error.
"""
import logging

import httpx

logger = logging.getLogger("app.voice")

BASE_URL = "https://seller.bulksmsplans.com/api"


def build_voice_provider(settings) -> "BulkSmsPlansVoiceProvider | None":
    """Construct the voice provider from an SmsSettings row, or None if the org
    isn't on BulkSMSPlans with credentials."""
    if not settings:
        return None
    provider = (getattr(settings, "provider", "") or "").lower()
    if provider not in ("bulksmsplans", "bulksms"):
        return None
    if not (settings.account_sid and settings.auth_token):
        return None
    return BulkSmsPlansVoiceProvider(settings.account_sid, settings.auth_token)


class BulkSmsPlansVoiceProvider:
    name = "bulksmsplans"

    def __init__(self, api_id: str, api_password: str):
        self.api_id = api_id
        self.api_password = api_password

    def _auth(self) -> dict:
        return {"api_id": self.api_id, "api_password": self.api_password}

    @staticmethod
    def _ok(payload) -> bool:
        return isinstance(payload, dict) and str(payload.get("code")) == "200"

    async def _post(self, path: str, body: dict, timeout: float = 20.0):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{BASE_URL}/{path}", json=body, timeout=timeout)
        return resp

    async def list_voice_media(self) -> dict:
        """Return {success, items:[...]} of the account's uploaded voice medias."""
        try:
            resp = await self._post("voice_media", self._auth())
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300], "items": []}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response", "items": []}
        return {"success": True, "items": payload.get("data") or []}

    async def add_voice_media(self, *, title: str, vendor_account_id: str, duration: str,
                              file_bytes: bytes, filename: str, content_type: str = "audio/mpeg") -> dict:
        """Upload a voice-media file (multipart). Returns {success, announcement_id, ...}."""
        data = {**self._auth(), "title": title, "vendor_account_id": str(vendor_account_id),
                "duration": str(duration)}
        files = {"voice_note": (filename, file_bytes, content_type)}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{BASE_URL}/add_voice_media", data=data, files=files, timeout=60.0)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300]}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}
        d = payload.get("data") or {}
        return {"success": True, "announcement_id": d.get("announcement_id"),
                "file_seconds": d.get("file_seconds"), "type": d.get("type"), "title": d.get("title")}

    async def send_voice_note(self, *, numbers: list[str], voice_type: str, voice_medias_id: str,
                              scheduled: bool = False, scheduled_datetime: str | None = None,
                              timezone_id: str | None = None, obd_type: str | None = None,
                              retry_interval: int | None = None, retry_count: int | None = None) -> dict:
        """OBD blast of a pre-recorded voice media to numbers. Returns {success, job_id?, raw}."""
        body = {**self._auth(), "number": ",".join(numbers), "voice_type": str(voice_type),
                "voice_medias_id": str(voice_medias_id), "scheduled": "1" if scheduled else "0"}
        if scheduled and scheduled_datetime:
            body["scheduled_datetime"] = scheduled_datetime
        if timezone_id:
            body["timezone_id"] = str(timezone_id)
        if obd_type:
            body["obd_type"] = obd_type
        if retry_interval is not None:
            body["retry_interval"] = str(retry_interval)
        if retry_count is not None:
            body["retry_count"] = str(retry_count)
        try:
            resp = await self._post("send_voice_note", body)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300]}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}
        d = payload.get("data") or {}
        return {"success": True, "job_id": d.get("job_id") or d.get("status"),
                "unique_ids": _split_ids(d.get("unique_ids")), "raw": d}

    async def send_tts(self, *, numbers: list[str], content: str,
                       language: str = "English", gender: str = "Male") -> dict:
        """Text-to-speech voice blast. Returns {success, job_id?, unique_ids:[...], raw}."""
        body = {**self._auth(), "number": ",".join(numbers), "content": content,
                "language": language, "gender": gender}
        try:
            resp = await self._post("send_tts", body)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300]}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}
        d = payload.get("data") or {}
        return {"success": True, "job_id": d.get("job_id"),
                "unique_ids": _split_ids(d.get("unique_ids")), "raw": d}

    async def fetch_report(self, unique_ids: list[str]) -> dict:
        """Voice DLR by unique id(s). Returns {success, rows:[...]}. """
        if not unique_ids:
            return {"success": True, "rows": []}
        try:
            resp = await self._post("voice/fetch_report", {**self._auth(), "unique_ids": ",".join(unique_ids)})
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300], "rows": []}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response", "rows": []}
        return {"success": True, "rows": payload.get("data") or []}

    async def voice_dlr_report(self, *, start_date: str | None = None, end_date: str | None = None,
                               msgstatus: str | None = None, phone_number: str | None = None) -> dict:
        """Voice DLR filtered by date/status/number. Returns {success, rows, total}."""
        body = {**self._auth()}
        if start_date:
            body["start_date"] = start_date
        if end_date:
            body["end_date"] = end_date
        if msgstatus:
            body["msgstatus"] = msgstatus
        if phone_number:
            body["phone_number"] = phone_number
        try:
            resp = await self._post("VoiceDLRReport", body)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300], "rows": [], "total": 0}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response", "rows": [], "total": 0}
        data = payload.get("data") or {}
        rows = data.get("data") if isinstance(data, dict) else data
        total = data.get("total") if isinstance(data, dict) else len(rows or [])
        return {"success": True, "rows": rows or [], "total": total or 0}

    async def missed_call_report(self, *, did_number: str, start_date: str, end_date: str) -> dict:
        """Missed-call alert report for a DID over a date range. Returns {success, rows}."""
        body = {**self._auth(), "did_number": did_number, "start_date": start_date, "end_date": end_date}
        try:
            resp = await self._post("missedcallalert-report", body)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300], "rows": []}
        if not self._ok(payload):
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response", "rows": []}
        data = payload.get("data")
        rows = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else [data] if data else [])
        return {"success": True, "rows": rows or []}


def _split_ids(raw) -> list[str]:
    """The API sometimes returns unique_ids as a comma-joined string (occasionally
    with stray quotes). Normalise to a clean list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip().strip('"') for x in raw if str(x).strip()]
    return [p.strip().strip('"') for p in str(raw).split(",") if p.strip()]


# Voice DLR status → canonical broadcast recipient status.
_VOICE_STATUS_MAP = {
    "answered": "answered", "dialed": "dialed", "hangup": "answered",
    "pending": "pending", "in process": "pending", "processing": "pending",
    "no answer": "no_answer", "no answered": "no_answer", "timeout ring": "no_answer",
    "busy": "busy", "congestion": "failed", "failed": "failed", "timeout": "failed",
    "timeout duration": "failed", "dnd": "failed", "rejected": "failed",
    "approved": "pending", "disapproved": "failed",
}


def map_voice_status(vendor_status: str | None) -> str | None:
    if not vendor_status:
        return None
    s = str(vendor_status).strip().lower()
    if s in _VOICE_STATUS_MAP:
        return _VOICE_STATUS_MAP[s]
    for key, mapped in _VOICE_STATUS_MAP.items():
        if key in s:
            return mapped
    return None

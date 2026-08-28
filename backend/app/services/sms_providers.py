"""Pluggable SMS provider layer.

Mirrors email_service's philosophy: a Mock provider that simulates delivery in
dev/CI without credentials, plus a real Twilio HTTP provider used when an org
configures one. Providers only transmit — persistence, retries, and webhooks
are handled by SmsService. A send returns an SmsSendResult; the provider never
raises for a business failure, it returns status='failed' with an error.
"""
import logging
import math
import re
import uuid
from dataclasses import dataclass

import httpx

logger = logging.getLogger("app.sms")

# GSM-7 single-segment is 160 chars; concatenated segments are 153 each.
def segment_count(text: str) -> int:
    n = len(text or "")
    if n <= 160:
        return 1
    return math.ceil(n / 153)


@dataclass
class SmsSendResult:
    status: str                    # queued|sent|failed
    provider_id: str | None = None
    error: str | None = None
    segments: int = 1


class BaseSmsProvider:
    name = "base"

    async def send(self, *, to_number: str, from_number: str, body: str) -> SmsSendResult:
        raise NotImplementedError


class MockSmsProvider:
    """Simulates a provider: logs the message and returns a queued result with a
    synthetic provider id. Used when provider='mock' or credentials are absent."""
    name = "mock"

    async def send(self, *, to_number: str, from_number: str, body: str) -> SmsSendResult:
        if not to_number:
            return SmsSendResult(status="failed", error="Missing destination number", segments=segment_count(body))
        provider_id = f"mock-{uuid.uuid4()}"
        logger.info("[SMS MOCK] to=%s from=%s body=%r id=%s", to_number, from_number, (body or "")[:80], provider_id)
        return SmsSendResult(status="queued", provider_id=provider_id, segments=segment_count(body))


class TwilioSmsProvider:
    """Real Twilio Messages API. account_sid/auth_token are the org's credentials;
    from_number is the org sender id. Network/HTTP errors become status='failed'
    so the caller can persist the error and retry later rather than 500."""
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str):
        self.account_sid = account_sid
        self.auth_token = auth_token

    async def send(self, *, to_number: str, from_number: str, body: str) -> SmsSendResult:
        segments = segment_count(body)
        if not (self.account_sid and self.auth_token):
            return SmsSendResult(status="failed", error="Twilio credentials not configured", segments=segments)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {"To": to_number, "From": from_number, "Body": body or ""}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=data, auth=(self.account_sid, self.auth_token), timeout=15.0)
            if 200 <= resp.status_code < 300:
                payload = resp.json()
                return SmsSendResult(status=payload.get("status") or "queued",
                                     provider_id=payload.get("sid"), segments=segments)
            # Twilio returns a JSON error body with a 'message' field
            try:
                err = resp.json().get("message") or resp.text
            except Exception:
                err = resp.text
            logger.warning("Twilio send failed: %s %s", resp.status_code, err)
            return SmsSendResult(status="failed", error=f"HTTP {resp.status_code}: {err}"[:500], segments=segments)
        except httpx.RequestError as exc:
            logger.error("Twilio connection error: %s", exc)
            return SmsSendResult(status="failed", error=f"Connection error: {exc}"[:500], segments=segments)


def normalize_indian_msisdn(number: str) -> str:
    """BhashSMS expects the mobile number WITHOUT the 91 country code (e.g.
    '9620194983'). Strip everything but digits, then drop a leading '91' country
    code or a leading trunk '0' so both '+91 96201 94983' and '09620194983'
    collapse to the bare 10-digit number the gateway wants."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


class BhashSmsProvider:
    """Real BhashSMS HTTP gateway (bhashsms.com/api/sendmsg.php).

    Credentials reuse the generic SmsSettings columns: account_sid holds the
    gateway `user`, auth_token holds `pass`, and sender_id is the approved
    `sender`. `stype` is auto-selected — 'unicode' when the body has non-ASCII
    characters (Hindi, emoji), else 'normal' — and priority defaults to 'ndnd'
    (transactional) which suits CRM notifications. The gateway returns a bare
    message id like 'S.45657' on success or a human error string on failure;
    network/HTTP errors become status='failed' so SmsService can persist + retry
    rather than 500. The password is never logged."""
    name = "bhash"
    BASE_URL = "http://bhashsms.com/api/sendmsg.php"
    _ERROR_MARKERS = ("invalid", "error", "insufficient", "fail", "wrong",
                      "blocked", "unauthor", "expired", "missing", "not ",
                      "please", "deactivat", "suspend")

    def __init__(self, user: str, password: str, priority: str = "ndnd"):
        self.user = user
        self.password = password
        self.priority = priority or "ndnd"

    async def send(self, *, to_number: str, from_number: str, body: str) -> SmsSendResult:
        segments = segment_count(body)
        if not (self.user and self.password):
            return SmsSendResult(status="failed", error="BhashSMS credentials not configured", segments=segments)
        if not from_number:
            return SmsSendResult(status="failed", error="BhashSMS sender id not configured", segments=segments)
        phone = normalize_indian_msisdn(to_number)
        if not phone:
            return SmsSendResult(status="failed", error="Missing/invalid destination number", segments=segments)
        stype = "normal" if (body or "").isascii() else "unicode"
        params = {
            "user": self.user,
            "pass": self.password,
            "sender": from_number,
            "phone": phone,
            "text": body or "",
            "priority": self.priority,
            "stype": stype,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.BASE_URL, params=params, timeout=20.0)
            text = (resp.text or "").strip()
            if 200 <= resp.status_code < 300 and text and not any(m in text.lower() for m in self._ERROR_MARKERS):
                # Success body is the message id (or comma-separated ids for bulk).
                provider_id = text.split(",")[0].strip()
                logger.info("[SMS BHASH] to=%s sender=%s id=%s stype=%s", phone, from_number, provider_id, stype)
                return SmsSendResult(status="sent", provider_id=provider_id, segments=segments)
            logger.warning("BhashSMS send failed: HTTP %s body=%r", resp.status_code, text[:200])
            return SmsSendResult(status="failed", error=f"HTTP {resp.status_code}: {text}"[:500], segments=segments)
        except httpx.RequestError as exc:
            logger.error("BhashSMS connection error: %s", exc)
            return SmsSendResult(status="failed", error=f"Connection error: {exc}"[:500], segments=segments)


# BulkSMSPlans vendor delivery/voice statuses → our canonical Activity.sms_status.
# The gateway is poll-based (no delivery webhook): status is fetched by message id.
_BULKSMS_STATUS_MAP = {
    "delivered": "delivered", "delivrd": "delivered", "success": "delivered",
    "sent": "sent", "submitted": "sent", "accepted": "sent",
    "pending": "sent", "in process": "sent", "queued": "sent", "processing": "sent",
    "failed": "failed", "rejected": "failed", "undeliv": "failed", "undelivered": "failed",
    "blocked": "failed", "blacklist": "failed", "expired": "failed", "dnd": "failed",
    "invalid": "failed", "error": "failed", "absent": "failed", "no answer": "failed",
}


def map_bulksms_status(vendor_status: str | None) -> str | None:
    """Map a BulkSMSPlans delivery status string to our canonical status, or None
    when unknown (caller then leaves the existing status untouched)."""
    if not vendor_status:
        return None
    s = str(vendor_status).strip().lower()
    if s in _BULKSMS_STATUS_MAP:
        return _BULKSMS_STATUS_MAP[s]
    for key, mapped in _BULKSMS_STATUS_MAP.items():
        if key in s:
            return mapped
    return None


class BulkSmsPlansProvider:
    """Real BulkSMSPlans gateway (seller.bulksmsplans.com).

    Credentials reuse the generic SmsSettings columns: account_sid holds the
    vendor `api_id`, auth_token holds `api_password`, and sender_id is the
    approved DLT `sender`. `sms_type` (Transactional|Promotional|OTP) and an
    optional DLT `template_id` come from settings. Encoding is auto-selected:
    '1' (text) for ASCII bodies, '2' (unicode) otherwise.

    The API answers JSON `{code, message, data}`; code 200 == success and
    data.message_id is the vendor id we persist. Unlike Twilio/Bhash there is no
    delivery webhook — status is polled later via :meth:`delivery_report`. All
    business/network failures become status='failed' so SmsService can retry
    rather than 500. The password is never logged."""
    name = "bulksmsplans"
    BASE_URL = "https://seller.bulksmsplans.com/api"

    def __init__(self, api_id: str, api_password: str,
                 sms_type: str = "Transactional", template_id: str | None = None):
        self.api_id = api_id
        self.api_password = api_password
        self.sms_type = sms_type or "Transactional"
        self.template_id = template_id or None

    def _auth(self) -> dict:
        return {"api_id": self.api_id, "api_password": self.api_password}

    @staticmethod
    def _encoding(body: str) -> str:
        # 1 = Text (GSM/ASCII), 2 = Unicode (Hindi, emoji, etc.).
        return "1" if (body or "").isascii() else "2"

    async def send(self, *, to_number: str, from_number: str, body: str) -> SmsSendResult:
        segments = segment_count(body)
        if not (self.api_id and self.api_password):
            return SmsSendResult(status="failed", error="BulkSMSPlans credentials not configured", segments=segments)
        if not from_number:
            return SmsSendResult(status="failed", error="BulkSMSPlans sender id not configured", segments=segments)
        phone = normalize_indian_msisdn(to_number)
        if not phone:
            return SmsSendResult(status="failed", error="Missing/invalid destination number", segments=segments)
        payload = {
            **self._auth(),
            "sms_type": self.sms_type,
            "sms_encoding": self._encoding(body),
            "sender": from_number,
            "number": phone,
            "message": body or "",
        }
        if self.template_id:
            payload["template_id"] = self.template_id
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/send_sms", json=payload, timeout=20.0)
            return self._parse_send(resp, phone, from_number, segments)
        except httpx.RequestError as exc:
            logger.error("BulkSMSPlans connection error: %s", exc)
            return SmsSendResult(status="failed", error=f"Connection error: {exc}"[:500], segments=segments)

    def _parse_send(self, resp, phone: str, sender: str, segments: int) -> SmsSendResult:
        try:
            payload = resp.json()
        except Exception:
            payload = None
        if resp.status_code >= 300 or not isinstance(payload, dict):
            body = (resp.text or "")[:200]
            logger.warning("BulkSMSPlans send failed: HTTP %s body=%r", resp.status_code, body)
            return SmsSendResult(status="failed", error=f"HTTP {resp.status_code}: {body}"[:500], segments=segments)
        code = payload.get("code")
        msg = payload.get("message") or ""
        if str(code) == "200":
            data = payload.get("data")
            mid = None
            if isinstance(data, dict):
                mid = data.get("message_id")
            elif isinstance(data, list) and data:
                mid = (data[0] or {}).get("message_id")
            logger.info("[SMS BULKSMSPLANS] to=%s sender=%s id=%s", phone, sender, mid)
            return SmsSendResult(status="sent", provider_id=str(mid) if mid is not None else None, segments=segments)
        logger.warning("BulkSMSPlans send rejected: code=%s message=%r", code, msg)
        return SmsSendResult(status="failed", error=f"[{code}] {msg}"[:500], segments=segments)

    async def delivery_report(self, message_id: str) -> dict:
        """Poll delivery status for one message id. Returns
        {found, status(mapped), vendor_status, error} — never raises."""
        if not message_id:
            return {"found": False, "error": "missing message id"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.BASE_URL}/sms_delivery_report",
                                        params={**self._auth(), "message_id": message_id}, timeout=15.0)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"found": False, "error": f"{exc}"[:300]}
        if not isinstance(payload, dict) or str(payload.get("code")) != "200":
            return {"found": False, "error": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}
        rows = payload.get("data") or []
        row = rows[0] if isinstance(rows, list) and rows else (rows if isinstance(rows, dict) else None)
        if not row:
            return {"found": False}
        vendor_status = row.get("status")
        return {"found": True, "status": map_bulksms_status(vendor_status),
                "vendor_status": vendor_status, "error": row.get("error_message") or None}

    async def send_otp(self, *, number: str, message: str, sender: str) -> dict:
        """Send a verification OTP. The vendor generates the code; `message` must
        contain the `{{otp}}` placeholder. Returns {success, message_id, error}."""
        if not (self.api_id and self.api_password):
            return {"success": False, "error": "BulkSMSPlans credentials not configured"}
        if not sender:
            return {"success": False, "error": "BulkSMSPlans sender id not configured"}
        phone = normalize_indian_msisdn(number)
        if not phone:
            return {"success": False, "error": "Missing/invalid destination number"}
        payload = {
            **self._auth(),
            "sms_type": self.sms_type,
            "sms_encoding": self._encoding(message),
            "sender": sender,
            "number": phone,
            "message": message,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/verify", json=payload, timeout=20.0)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"{exc}"[:300]}
        if isinstance(data, dict) and str(data.get("code")) == "200":
            mid = (data.get("data") or {}).get("message_id")
            return {"success": True, "message_id": str(mid) if mid is not None else None}
        msg = (data or {}).get("message") if isinstance(data, dict) else "bad response"
        return {"success": False, "error": f"[{(data or {}).get('code')}] {msg}"[:300]}

    async def verify_otp(self, *, message_id: str, otp: str) -> dict:
        """Verify a user-entered OTP against a prior send. Returns {success, verified, message}."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/verify_status",
                                         json={**self._auth(), "message_id": message_id, "otp": otp}, timeout=15.0)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "verified": False, "message": f"{exc}"[:300]}
        ok = isinstance(data, dict) and str(data.get("code")) == "200"
        return {"success": ok, "verified": ok,
                "message": (data or {}).get("message") if isinstance(data, dict) else "bad response"}

    async def check_balance(self) -> dict:
        """Fetch account balance. Returns {success, amount, currency, message}."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/check_balance", json=self._auth(), timeout=15.0)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300]}
        if not isinstance(payload, dict) or str(payload.get("code")) != "200":
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}
        data = payload.get("data") or []
        row = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        return {"success": True, "amount": row.get("BalanceAmount"),
                "currency": row.get("CurrenceCode") or row.get("CurrencyCode") or "INR"}

    async def list_sender_ids(self) -> dict:
        """Fetch approved/pending sender IDs. Returns {success, items:[{sender_id,country,status}]}."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/get_sender_request_list", json=self._auth(), timeout=15.0)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300], "items": []}
        if not isinstance(payload, dict) or str(payload.get("code")) != "200":
            return {"success": False, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response", "items": []}
        data = payload.get("data") or {}
        items = data.get("data") if isinstance(data, dict) else data
        return {"success": True, "items": items or []}

    async def request_sender_id(self, sender: str, country: str = "India", remarks: str | None = None) -> dict:
        """Submit a new sender-ID approval request. Returns {success, message}."""
        body = {**self._auth(), "sender": sender, "country": country}
        if remarks:
            body["remarks"] = remarks
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.BASE_URL}/sender_request", json=body, timeout=15.0)
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"{exc}"[:300]}
        ok = isinstance(payload, dict) and str(payload.get("code")) == "200"
        return {"success": ok, "message": (payload or {}).get("message") if isinstance(payload, dict) else "bad response"}


def build_bulksmsplans(settings) -> BulkSmsPlansProvider:
    """Construct a BulkSMSPlans provider from an SmsSettings row (creds required)."""
    return BulkSmsPlansProvider(
        settings.account_sid, settings.auth_token,
        sms_type=(getattr(settings, "sms_type", None) or "Transactional"),
        template_id=(getattr(settings, "default_template_id", None) or None),
    )


def get_provider(settings) -> "MockSmsProvider | TwilioSmsProvider | BhashSmsProvider | BulkSmsPlansProvider":
    """Resolve a provider instance from an SmsSettings row. Falls back to Mock
    when the row is missing, inactive, or lacks credentials for a real provider."""
    if not settings or not settings.is_active:
        return MockSmsProvider()
    provider = (settings.provider or "mock").lower()
    if provider == "twilio" and settings.account_sid and settings.auth_token:
        return TwilioSmsProvider(settings.account_sid, settings.auth_token)
    if provider in ("bhash", "bhashsms") and settings.account_sid and settings.auth_token:
        return BhashSmsProvider(settings.account_sid, settings.auth_token,
                                priority=(getattr(settings, "sms_priority", None) or "ndnd"))
    if provider in ("bulksmsplans", "bulksms") and settings.account_sid and settings.auth_token:
        return build_bulksmsplans(settings)
    return MockSmsProvider()

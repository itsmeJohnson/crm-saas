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


def get_provider(settings) -> "MockSmsProvider | TwilioSmsProvider | BhashSmsProvider":
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
    return MockSmsProvider()

"""Pluggable SMS provider layer.

Mirrors email_service's philosophy: a Mock provider that simulates delivery in
dev/CI without credentials, plus a real Twilio HTTP provider used when an org
configures one. Providers only transmit — persistence, retries, and webhooks
are handled by SmsService. A send returns an SmsSendResult; the provider never
raises for a business failure, it returns status='failed' with an error.
"""
import logging
import math
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


def get_provider(settings) -> "MockSmsProvider | TwilioSmsProvider":
    """Resolve a provider instance from an SmsSettings row. Falls back to Mock
    when the row is missing, inactive, or lacks credentials for a real provider."""
    if not settings or not settings.is_active:
        return MockSmsProvider()
    provider = (settings.provider or "mock").lower()
    if provider == "twilio" and settings.account_sid and settings.auth_token:
        return TwilioSmsProvider(settings.account_sid, settings.auth_token)
    return MockSmsProvider()

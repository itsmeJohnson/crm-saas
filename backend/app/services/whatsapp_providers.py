"""Pluggable WhatsApp provider layer.

Mirrors sms_providers/email_service: a Mock provider that simulates delivery in
dev/CI without credentials, plus a real Meta WhatsApp Cloud API provider used
when an org configures one. Providers only transmit; persistence, the 24h
window, auto-reply, and webhooks are handled by WhatsAppService. A send never
raises for a business failure — it returns status='failed' with an error.
"""
import logging
import uuid
from dataclasses import dataclass

import httpx

logger = logging.getLogger("app.whatsapp")

META_GRAPH_VERSION = "v19.0"


@dataclass
class WaSendResult:
    status: str                      # sent|failed
    message_id: str | None = None
    error: str | None = None


class MockWhatsAppProvider:
    """Simulates the WhatsApp Cloud API: logs and returns a synthetic WAMID."""
    name = "mock"

    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        return self._simulate(to_number, "text")

    async def send_template(self, *, to_number: str, template_name: str, body: str) -> WaSendResult:
        return self._simulate(to_number, f"template:{template_name}")

    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None) -> WaSendResult:
        if not media_url:
            return WaSendResult(status="failed", error="Missing media url")
        return self._simulate(to_number, f"media:{media_type}")

    def _simulate(self, to_number: str, kind: str) -> WaSendResult:
        if not to_number:
            return WaSendResult(status="failed", error="Missing destination number")
        wamid = f"wamid.mock-{uuid.uuid4()}"
        logger.info("[WA MOCK] to=%s kind=%s id=%s", to_number, kind, wamid)
        return WaSendResult(status="sent", message_id=wamid)


class MetaWhatsAppProvider:
    """Meta WhatsApp Cloud API (graph.facebook.com). Network/HTTP errors become
    status='failed' so the caller can persist the error rather than 500."""
    name = "meta"

    def __init__(self, phone_number_id: str, access_token: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    @property
    def _url(self) -> str:
        return f"https://graph.facebook.com/{META_GRAPH_VERSION}/{self.phone_number_id}/messages"

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def _post(self, payload: dict) -> WaSendResult:
        if not (self.phone_number_id and self.access_token):
            return WaSendResult(status="failed", error="Meta WhatsApp credentials not configured")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._url, json=payload, headers=self._headers, timeout=15.0)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                msgs = data.get("messages") or []
                mid = msgs[0].get("id") if msgs else None
                return WaSendResult(status="sent", message_id=mid)
            try:
                err = resp.json().get("error", {}).get("message") or resp.text
            except Exception:
                err = resp.text
            logger.warning("Meta WA send failed: %s %s", resp.status_code, err)
            return WaSendResult(status="failed", error=f"HTTP {resp.status_code}: {err}"[:500])
        except httpx.RequestError as exc:
            logger.error("Meta WA connection error: %s", exc)
            return WaSendResult(status="failed", error=f"Connection error: {exc}"[:500])

    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        return await self._post({"messaging_product": "whatsapp", "to": to_number,
                                 "type": "text", "text": {"body": body}})

    async def send_template(self, *, to_number: str, template_name: str, body: str) -> WaSendResult:
        # Minimal template send; components/params can be extended per template.
        return await self._post({"messaging_product": "whatsapp", "to": to_number,
                                 "type": "template",
                                 "template": {"name": template_name, "language": {"code": "en_US"}}})

    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None) -> WaSendResult:
        # media_type is one of image|video|document|audio
        obj: dict = {"link": media_url}
        if caption and media_type in ("image", "video", "document"):
            obj["caption"] = caption
        return await self._post({"messaging_product": "whatsapp", "to": to_number,
                                 "type": media_type, media_type: obj})


def get_provider(settings) -> "MockWhatsAppProvider | MetaWhatsAppProvider":
    """Resolve a provider from a WhatsAppSettings row. Falls back to Mock when the
    row is missing, inactive, or lacks Meta credentials."""
    if not settings or not settings.is_active:
        return MockWhatsAppProvider()
    provider = (settings.provider or "mock").lower()
    if provider == "meta" and settings.phone_number_id and settings.access_token:
        return MetaWhatsAppProvider(settings.phone_number_id, settings.access_token)
    return MockWhatsAppProvider()

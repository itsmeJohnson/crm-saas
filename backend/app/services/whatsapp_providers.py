"""Pluggable WhatsApp provider layer.

Follows SOLID and Open/Closed principles: all provider integrations sit behind the
generic WhatsAppProvider interface. Supports capability flagging, media operations,
template syncing, and dynamic health-checks.
"""
import logging
import uuid
import json
from dataclasses import dataclass
from abc import ABC, abstractmethod
import httpx

logger = logging.getLogger("app.whatsapp")

META_GRAPH_VERSION = "v19.0"


@dataclass
class WaSendResult:
    status: str                      # sent|failed
    message_id: str | None = None
    error: str | None = None


class WhatsAppProvider(ABC):
    """Abstract Base Class (Interface) for WhatsApp providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass

    # Provider capabilities flags
    @property
    @abstractmethod
    def supports_templates(self) -> bool: pass

    @property
    @abstractmethod
    def supports_reactions(self) -> bool: pass

    @property
    @abstractmethod
    def supports_location(self) -> bool: pass

    @property
    @abstractmethod
    def supports_contacts(self) -> bool: pass

    @property
    @abstractmethod
    def supports_catalog(self) -> bool: pass

    @property
    @abstractmethod
    def supports_payments(self) -> bool: pass

    @abstractmethod
    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        pass

    @abstractmethod
    async def send_template(self, *, to_number: str, template_name: str, language: str, variables: list | None = None) -> WaSendResult:
        pass

    @abstractmethod
    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None = None, file_name: str | None = None) -> WaSendResult:
        pass

    @abstractmethod
    async def upload_media(self, *, content: bytes, mime_type: str, file_name: str) -> str:
        """Uploads media asset to the provider and returns the provider's media ID."""
        pass

    @abstractmethod
    async def download_media(self, *, media_id: str) -> bytes:
        """Downloads raw binary file media from the provider."""
        pass

    @abstractmethod
    async def mark_as_read(self, *, message_id: str) -> bool:
        """Sends read receipt status back to the provider."""
        pass

    @abstractmethod
    async def sync_templates(self) -> list[dict]:
        """Fetches approved message templates definitions from the provider API."""
        pass

    @abstractmethod
    async def check_health(self) -> str:
        """Performs check against provider API.

        Returns: connected|disconnected|rate_limited|expired_token|maintenance
        """
        pass


class MockWhatsAppProvider(WhatsAppProvider):
    """Simulates the WhatsApp Cloud API: logs actions and returns synthetic IDs in dev/CI."""
    
    @property
    def name(self) -> str: return "mock"
    @property
    def supports_templates(self) -> bool: return True
    @property
    def supports_reactions(self) -> bool: return True
    @property
    def supports_location(self) -> bool: return True
    @property
    def supports_contacts(self) -> bool: return True
    @property
    def supports_catalog(self) -> bool: return False
    @property
    def supports_payments(self) -> bool: return False

    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        return self._simulate(to_number, "text")

    async def send_template(self, *, to_number: str, template_name: str, language: str, variables: list | None = None) -> WaSendResult:
        return self._simulate(to_number, f"template:{template_name} (lang={language}, vars={variables})")

    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None = None, file_name: str | None = None) -> WaSendResult:
        if not media_url:
            return WaSendResult(status="failed", error="Missing media url")
        return self._simulate(to_number, f"media:{media_type} ({file_name or 'file'})")

    async def upload_media(self, *, content: bytes, mime_type: str, file_name: str) -> str:
        mock_id = f"mock-media-{uuid.uuid4()}"
        logger.info("[WA MOCK] upload_media filename=%s size=%d id=%s", file_name, len(content), mock_id)
        return mock_id

    async def download_media(self, *, media_id: str) -> bytes:
        logger.info("[WA MOCK] download_media id=%s", media_id)
        return b"Mock binary media content placeholder"

    async def mark_as_read(self, *, message_id: str) -> bool:
        logger.info("[WA MOCK] mark_as_read message_id=%s", message_id)
        return True

    async def sync_templates(self) -> list[dict]:
        logger.info("[WA MOCK] sync_templates")
        return [
            {
                "id": "mock-template-welcome",
                "name": "welcome",
                "category": "UTILITY",
                "language": "en_US",
                "status": "APPROVED",
                "body_text": "Welcome to our service! We are glad to have you.",
            },
            {
                "id": "mock-template-offer",
                "name": "seasonal_offer",
                "category": "MARKETING",
                "language": "en_US",
                "status": "APPROVED",
                "body_text": "Special discount for you: {{1}} off! Valid till {{2}}.",
                "header_format": "TEXT",
                "header_text": "Exclusive Deal",
                "footer_text": "T&C Apply",
            }
        ]

    async def check_health(self) -> str:
        return "connected"

    def _simulate(self, to_number: str, kind: str) -> WaSendResult:
        if not to_number:
            return WaSendResult(status="failed", error="Missing destination number")
        wamid = f"wamid.mock-{uuid.uuid4()}"
        logger.info("[WA MOCK] to=%s kind=%s id=%s", to_number, kind, wamid)
        return WaSendResult(status="sent", message_id=wamid)


class MetaWhatsAppProvider(WhatsAppProvider):
    """Meta WhatsApp Cloud API integration using Facebook Graph API endpoint."""

    def __init__(self, phone_number_id: str, business_account_id: str, access_token: str, api_version: str = "v19.0"):
        self.phone_number_id = phone_number_id
        self.business_account_id = business_account_id
        self.access_token = access_token
        self.api_version = api_version or "v19.0"

    @property
    def name(self) -> str: return "meta"
    @property
    def supports_templates(self) -> bool: return True
    @property
    def supports_reactions(self) -> bool: return True
    @property
    def supports_location(self) -> bool: return True
    @property
    def supports_contacts(self) -> bool: return True
    @property
    def supports_catalog(self) -> bool: return False
    @property
    def supports_payments(self) -> bool: return False

    @property
    def _messages_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def _post(self, url: str, payload: dict) -> WaSendResult:
        if not (self.phone_number_id and self.access_token):
            return WaSendResult(status="failed", error="Meta credentials not configured")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=self._headers, timeout=15.0)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                msgs = data.get("messages") or []
                mid = msgs[0].get("id") if msgs else None
                return WaSendResult(status="sent", message_id=mid)
            try:
                err = resp.json().get("error", {}).get("message") or resp.text
            except Exception:
                err = resp.text
            logger.warning("Meta WA request failed (%s): %s", resp.status_code, err)
            
            # Translate rate limit errors
            if resp.status_code == 429:
                return WaSendResult(status="failed", error="Rate limited by Meta Business API")
            
            return WaSendResult(status="failed", error=f"HTTP {resp.status_code}: {err}"[:500])
        except httpx.RequestError as exc:
            logger.error("Meta WA networking exception: %s", exc)
            return WaSendResult(status="failed", error=f"Connection failure: {exc}"[:500])

    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"preview_url": True, "body": body}
        }
        return await self._post(self._messages_url, payload)

    async def send_template(self, *, to_number: str, template_name: str, language: str, variables: list | None = None) -> WaSendResult:
        components = []
        if variables:
            parameters = [{"type": "text", "text": str(v)} for v in variables]
            components.append({
                "type": "body",
                "parameters": parameters
            })
            
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components
            }
        }
        return await self._post(self._messages_url, payload)

    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None = None, file_name: str | None = None) -> WaSendResult:
        obj = {"link": media_url}
        if caption and media_type in ("image", "video", "document"):
            obj["caption"] = caption
        if file_name and media_type == "document":
            obj["filename"] = file_name

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": media_type,
            media_type: obj
        }
        return await self._post(self._messages_url, payload)

    async def upload_media(self, *, content: bytes, mime_type: str, file_name: str) -> str:
        if self.access_token.startswith("EAAG_mock"):
            return "mock_media_id_12345"
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/media"
        files = {
            "file": (file_name, content, mime_type)
        }
        data = {
            "messaging_product": "whatsapp"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, files=files, data=data, headers=self._headers, timeout=30.0)
        if resp.status_code >= 300:
            raise RuntimeError(f"Meta media upload failed: {resp.text}")
        return resp.json()["id"]

    async def delete_media(self, *, media_id: str) -> bool:
        if self.access_token.startswith("EAAG_mock"):
            return True
        url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers, timeout=15.0)
        return resp.status_code == 200

    async def download_media(self, *, media_id: str) -> bytes:
        # Step 1: Resolve Meta media node to retrieve CDN URL
        url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=15.0)
        if resp.status_code >= 300:
            raise RuntimeError(f"Meta media node resolution failed: {resp.text}")
        
        cdn_url = resp.json()["url"]
        
        # Step 2: Download raw binary asset using Bearer Auth header
        async with httpx.AsyncClient() as client:
            media_resp = await client.get(cdn_url, headers=self._headers, timeout=30.0)
        if media_resp.status_code >= 300:
            raise RuntimeError(f"Meta binary asset download failed: {media_resp.text}")
        
        return media_resp.content

    async def mark_as_read(self, *, message_id: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        res = await self._post(self._messages_url, payload)
        return res.status == "sent"

    async def sync_templates(self) -> list[dict]:
        if self.access_token.startswith("EAAG_mock"):
            return [
                {
                    "meta_template_id": "mock_template_welcome_1",
                    "name": "welcome_message",
                    "category": "UTILITY",
                    "language": "en_US",
                    "status": "APPROVED",
                    "header_format": "TEXT",
                    "header_text": "Hello!",
                    "body_text": "Welcome to our customer portal. We look forward to serving you.",
                    "footer_text": "Support Team",
                    "buttons": []
                }
            ]
        if not self.business_account_id:
            raise ValueError("business_account_id is required to sync templates")
        url = f"https://graph.facebook.com/{self.api_version}/{self.business_account_id}/message_templates"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=20.0)
        if resp.status_code >= 300:
            raise RuntimeError(f"Meta templates sync failed: {resp.text}")
        
        templates = []
        for t in resp.json().get("data", []):
            # Parse template components to fetch structure definitions
            body_text = ""
            header_format = None
            header_text = None
            footer_text = None
            buttons = {}
            
            for comp in t.get("components", []):
                ctype = comp.get("type")
                if ctype == "BODY":
                    body_text = comp.get("text", "")
                elif ctype == "HEADER":
                    header_format = comp.get("format")
                    header_text = comp.get("text")
                elif ctype == "FOOTER":
                    footer_text = comp.get("text")
                elif ctype == "BUTTONS":
                    buttons = comp.get("buttons", [])

            templates.append({
                "meta_template_id": t.get("id"),
                "name": t.get("name"),
                "category": t.get("category"),
                "language": t.get("language"),
                "status": t.get("status"),
                "header_format": header_format,
                "header_text": header_text,
                "body_text": body_text,
                "footer_text": footer_text,
                "buttons": buttons
            })
        return templates

    async def check_health(self) -> str:
        if self.access_token.startswith("EAAG_mock") or self.access_token == "mock_access_token":
            return "connected"
        # Hit /me Graph API node with token to check for credentials expiration
        url = f"https://graph.facebook.com/{self.api_version}/me"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers, timeout=10.0)
            if resp.status_code == 200:
                return "connected"
            if resp.status_code == 401:
                return "expired_token"
            if resp.status_code == 429:
                return "rate_limited"
            return "disconnected"
        except Exception:
            return "disconnected"

    # Embedded Signup & Discovery Helpers
    async def exchange_auth_code(self, *, app_id: str, app_secret: str, redirect_uri: str, code: str) -> str:
        """Exchanges authorization code for system user / business access token."""
        if code.startswith("mock_"):
            return f"EAAG_mock_{code}"
        url = f"https://graph.facebook.com/{self.api_version}/oauth/access_token"
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "client_secret": app_secret,
            "code": code
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15.0)
        if resp.status_code >= 300:
            raise RuntimeError(f"OAuth code exchange failed: {resp.text}")
        return resp.json()["access_token"]

    async def fetch_waba_phone_numbers(self, *, waba_id: str) -> list[dict]:
        """Fetches phone numbers configured under a specific WABA ID."""
        if self.access_token.startswith("EAAG_mock") or waba_id.startswith("waba_mock"):
            return [
                {
                    "id": "phone_mock_1",
                    "display_phone_number": "+15555555555",
                    "verified_name": "Primary Support Line",
                    "quality_rating": "GREEN",
                    "messaging_limit_tier": "TIER_1K",
                    "display_name_status": "APPROVED"
                },
                {
                    "id": "phone_mock_2",
                    "display_phone_number": "+15555551234",
                    "verified_name": "Sales Department",
                    "quality_rating": "GREEN",
                    "messaging_limit_tier": "TIER_10K",
                    "display_name_status": "APPROVED"
                }
            ]
        url = f"https://graph.facebook.com/{self.api_version}/{waba_id}/phone_numbers"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=15.0)
        if resp.status_code >= 300:
            raise RuntimeError(f"Failed to fetch phone numbers for WABA {waba_id}: {resp.text}")
        return resp.json().get("data", [])

    async def fetch_shared_wabas(self) -> list[dict]:
        """Fetches WABAs associated with the token user/system account."""
        if self.access_token.startswith("EAAG_mock"):
            return [{"id": "waba_mock_waba123", "name": "Mock WABA Business"}]
        url = f"https://graph.facebook.com/{self.api_version}/me/client_whatsapp_business_accounts"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=15.0)
        if resp.status_code >= 300:
            # Fallback to direct accounts query
            url_alt = f"https://graph.facebook.com/{self.api_version}/me/accounts"
            async with httpx.AsyncClient() as client_alt:
                resp_alt = await client_alt.get(url_alt, headers=self._headers, timeout=15.0)
            if resp_alt.status_code >= 300:
                raise RuntimeError(f"Failed to fetch WhatsApp Business Accounts: {resp_alt.text}")
            return resp_alt.json().get("data", [])
        return resp.json().get("data", [])


def get_provider(settings) -> WhatsAppProvider:
    """Factory function: resolves the active provider class from a settings row."""
    if not settings or not settings.is_active:
        return MockWhatsAppProvider()
    
    provider_name = (settings.provider or "mock").lower()
    if provider_name == "meta" and settings.phone_number_id and settings.access_token:
        # Settings access_token decryption is completed at caller layer (whatsapp_service.py)
        return MetaWhatsAppProvider(
            phone_number_id=settings.phone_number_id,
            business_account_id=settings.business_account_id or "",
            access_token=settings.access_token,
            api_version=settings.api_version or "v19.0"
        )
    return MockWhatsAppProvider()

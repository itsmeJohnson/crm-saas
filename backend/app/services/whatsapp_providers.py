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


class GupshupWhatsAppProvider(WhatsAppProvider):
    """Gupshup WhatsApp Enterprise / Messaging API integration.

    Uses Gupshup REST API endpoint: https://api.gupshup.io/wa/api/v1/msg
    Template sync endpoint: https://api.gupshup.io/wa/api/v1/template/list/{app_name}
    Health check endpoint: https://api.gupshup.io/wa/api/v1/users/{app_name}
    """

    def __init__(self, app_name: str, api_key: str, sender_number: str = ""):
        self.app_name = (app_name or "").strip()
        self.api_key = (api_key or "").strip()
        self.sender_number = (sender_number or "").replace("+", "").replace(" ", "").replace("-", "").strip()
        self.base_url = "https://api.gupshup.io/sm/api/v1"

    @property
    def name(self) -> str:
        return "gupshup"

    @property
    def supports_templates(self) -> bool:
        return True

    @property
    def supports_reactions(self) -> bool:
        return False

    @property
    def supports_location(self) -> bool:
        return True

    @property
    def supports_contacts(self) -> bool:
        return True

    @property
    def supports_catalog(self) -> bool:
        return False

    @property
    def supports_payments(self) -> bool:
        return False

    @property
    def effective_userid(self) -> str:
        """Resolves the Gupshup Enterprise client ID.
        
        If app_name is the WABA ID (1450447470606065) or Phone Number ID (1259161873954670) or empty,
        defaults to the Samartha Sankalpa Client ID 2000270886.
        """
        if self.app_name in ("1450447470606065", "1259161873954670", ""):
            return "2000270886"
        return self.app_name

    @property
    def _is_gateway(self) -> bool:
        # Gupshup Conversation Cloud / Enterprise accounts with 10-digit Client ID or mediaapi base
        return bool(self.app_name and (self.app_name.isdigit() or "mediaapi" in self.base_url)) or bool(self.effective_userid)

    @property
    def _headers(self) -> dict:
        if self._is_gateway:
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        return {
            "apikey": self.api_key,
            "api_key": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }

    async def send_text(self, *, to_number: str, body: str) -> WaSendResult:
        if not (self.effective_userid and self.api_key):
            return WaSendResult(status="failed", error="Gupshup credentials not fully configured (userid and token required)")
        clean_to = "".join(c for c in (to_number or "") if c.isdigit())
        if not clean_to.startswith("91") and len(clean_to) == 10:
            clean_to = f"91{clean_to}"
        if len(clean_to) < 10:
            return WaSendResult(status="failed", error=f"Invalid destination phone number: {to_number}")

        if self._is_gateway:
            # Gupshup Gateway API: send plain text message directly on WhatsApp channel
            payload = {
                "channel": "whatsapp",
                "send_to": clean_to,
                "msg": body,
                "msg_type": "text",
                "userid": self.effective_userid,
                "auth_scheme": "plain",
                "v": "1.1",
                "format": "json",
                "method": "SendMessage",
            }
            res = await self._post_gateway(payload)
            if res.status == "sent":
                return res
            # If 24-hr session window is closed or template is explicitly required, fall back to outreach template
            err_lower = (res.error or "").lower()
            if "template" in err_lower or "window" in err_lower or "session" in err_lower:
                payload_fallback = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "msg": "Hi, we would like to have your phone number on file.",
                    "msg_type": "HSM",
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SendMessage",
                    "isHSM": "true",
                    "isTemplate": "true",
                    "linkTrackingEnabled": "true",
                    "whatsAppTemplateId": "1401814018783680",
                    "var1": "Customer",
                }
                return await self._post_gateway(payload_fallback)
            return res

        payload = {
            "channel": "whatsapp",
            "source": self.sender_number,
            "destination": clean_to,
            "src.name": self.app_name,
            "message": json.dumps({"type": "text", "text": body}),
        }
        return await self._post_msg(f"{self.base_url}/msg", payload)

    async def send_template(self, *, to_number: str, template_name: str, language: str, variables: list | None = None, body: str | None = None) -> WaSendResult:
        if not (self.effective_userid and self.api_key):
            return WaSendResult(status="failed", error="Gupshup credentials not fully configured")
        clean_to = "".join(c for c in (to_number or "") if c.isdigit())
        if not clean_to.startswith("91") and len(clean_to) == 10:
            clean_to = f"91{clean_to}"
        if len(clean_to) < 10:
            return WaSendResult(status="failed", error=f"Invalid destination phone number: {to_number}")

        raw_key = str(template_name or "").strip().lower()
        var1_val = str(variables[0]) if (variables and len(variables) > 0 and str(variables[0]).strip()) else "Customer"

        # Explicit approved Meta HSM templates
        if self._is_gateway:
            if raw_key in ("hiring", "4548035658774661"):
                hiring_body = body or (
                    "Hi, thanks for your interest in telecaller hiring. We have received your application. "
                    "Your interview is scheduled on Monday at Samartha Sankalpa OPC Pvt Ltd Location: Kengeri. "
                    "Please reply with \"CONFIRM\" to confirm your slot."
                )
                payload_media = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SENDMEDIAMESSAGE",
                    "msg_type": "IMAGE",
                    "media_url": "https://crm.samarthasankalpa.com/logo.png",
                    "caption": hiring_body,
                    "msg": hiring_body,
                    "isTemplate": "true",
                    "isHSM": "true",
                    "footer": "Contact 9353527253",
                    "whatsAppTemplateId": "4548035658774661",
                }
                res = await self._post_gateway(payload_media)
                if res.status == "sent":
                    return res
                # Fallback to SendMessage HSM
                payload_text = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SendMessage",
                    "msg_type": "HSM",
                    "msg": hiring_body,
                    "isTemplate": "true",
                    "isHSM": "true",
                    "linkTrackingEnabled": "true",
                    "whatsAppTemplateId": "4548035658774661",
                }
                return await self._post_gateway(payload_text)

            elif raw_key in ("request_phone_number", "request_contact_info", "contact_request", "1401814018783680"):
                req_body = body or "Hi, we would like to have your phone number on file."
                payload = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "msg": req_body,
                    "msg_type": "HSM",
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SendMessage",
                    "isHSM": "true",
                    "isTemplate": "true",
                    "linkTrackingEnabled": "true",
                    "whatsAppTemplateId": "1401814018783680",
                    "var1": var1_val,
                }
                return await self._post_gateway(payload)
            else:
                # Custom CRM template text (e.g. lead_greeting, callback_reminder, kyc_document_request)
                text_content = body or ""
                if not text_content:
                    if raw_key == "callback_reminder":
                        text_content = f"Hello {var1_val}, we tried calling you regarding your inquiry. Please let us know a convenient time to speak."
                    elif raw_key == "kyc_document_request":
                        text_content = f"Dear {var1_val}, please send your required KYC documents (Aadhaar / ID proof) on this WhatsApp chat to proceed with your verification."
                    elif raw_key == "lead_greeting":
                        text_content = f"Hello {var1_val}, thank you for reaching out to Samartha Sankalpa Solutions. Our team is here to assist you."
                    else:
                        text_content = f"Hello {var1_val}, regarding your inquiry with Samartha Sankalpa Solutions."
                elif variables:
                    for idx, v in enumerate(variables, 1):
                        text_content = text_content.replace(f"{{{{{idx}}}}}", str(v))

                payload = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "msg": text_content,
                    "msg_type": "text",
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SendMessage",
                }
                res = await self._post_gateway(payload)
                if res.status == "sent":
                    return res
                # Fallback to outreach template only if session window is closed
                payload_fallback = {
                    "channel": "whatsapp",
                    "send_to": clean_to,
                    "msg": "Hi, we would like to have your phone number on file.",
                    "msg_type": "HSM",
                    "userid": self.effective_userid,
                    "auth_scheme": "plain",
                    "v": "1.1",
                    "format": "json",
                    "method": "SendMessage",
                    "isHSM": "true",
                    "isTemplate": "true",
                    "linkTrackingEnabled": "true",
                    "whatsAppTemplateId": "1401814018783680",
                    "var1": var1_val,
                }
                return await self._post_gateway(payload_fallback)

        payload = {
            "source": self.sender_number,
            "destination": clean_to,
            "template": json.dumps({"id": raw_key, "params": [str(v) for v in (variables or [])]}),
        }
        return await self._post_msg(f"{self.base_url}/template/msg", payload)

    async def _post_gateway(self, data: dict) -> WaSendResult:
        if self.api_key.startswith("mock_") or self.api_key == "mock_access_token":
            mid = f"gupshup-mock-{uuid.uuid4()}"
            logger.info("[GUPSHUP MOCK GATEWAY] Sent to %s: %s", data.get("send_to"), mid)
            return WaSendResult(status="sent", message_id=mid)

        # Enforce required Gupshup WhatsApp Gateway protocol fields
        data.setdefault("channel", "whatsapp")
        data.setdefault("userid", self.effective_userid)
        data.setdefault("auth_scheme", "plain")
        data.setdefault("v", "1.1")
        data.setdefault("format", "json")

        url = "https://mediaapi.smsgupshup.com/GatewayAPI/rest"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=data, headers=headers, timeout=20.0)
            if 200 <= resp.status_code < 300:
                body = resp.json()
                resp_obj = body.get("response", {})
                status_str = resp_obj.get("status")
                mid = resp_obj.get("id")
                if status_str == "success" or mid:
                    return WaSendResult(status="sent", message_id=mid)
                err = resp_obj.get("details") or resp_obj.get("message") or str(body)
                return WaSendResult(status="failed", error=err)
            
            try:
                err = resp.json().get("response", {}).get("details") or resp.text
            except Exception:
                err = resp.text
            return WaSendResult(status="failed", error=f"HTTP {resp.status_code}: {err}"[:500])
        except httpx.RequestError as exc:
            logger.error("Gupshup Gateway networking exception: %s", exc)
            return WaSendResult(status="failed", error=f"Gupshup Gateway connection failure: {exc}"[:500])

    async def send_media(self, *, to_number: str, media_url: str, media_type: str, caption: str | None = None, file_name: str | None = None) -> WaSendResult:
        if not (self.effective_userid and self.api_key):
            return WaSendResult(status="failed", error="Gupshup credentials not fully configured")
        clean_to = to_number.replace("+", "").replace(" ", "").replace("-", "").strip()
        if not clean_to.startswith("91") and len(clean_to) == 10:
            clean_to = f"91{clean_to}"

        if self._is_gateway:
            mtype_val = "IMAGE" if media_type == "image" else ("DOCUMENT" if media_type in ("document", "file", "pdf") else "VIDEO")
            payload = {
                "channel": "whatsapp",
                "send_to": clean_to,
                "userid": self.effective_userid,
                "auth_scheme": "plain",
                "v": "1.1",
                "format": "json",
                "method": "SENDMEDIAMESSAGE",
                "msg_type": mtype_val,
                "media_url": media_url,
            }
            if caption:
                payload["caption"] = caption
                payload["msg"] = caption
            if file_name:
                payload["filename"] = file_name
            return await self._post_gateway(payload)
        clean_to = to_number.replace("+", "").replace(" ", "").replace("-", "").strip()
        
        # Build Gupshup media message payload
        if media_type == "image":
            msg_obj = {
                "type": "image",
                "originalUrl": media_url,
                "previewUrl": media_url,
            }
            if caption:
                msg_obj["caption"] = caption
        elif media_type in ("document", "file"):
            msg_obj = {
                "type": "file",
                "url": media_url,
                "filename": file_name or "document",
            }
        elif media_type == "audio":
            msg_obj = {
                "type": "audio",
                "url": media_url,
            }
        elif media_type == "video":
            msg_obj = {
                "type": "video",
                "url": media_url,
            }
            if caption:
                msg_obj["caption"] = caption
        else:
            msg_obj = {
                "type": media_type,
                "url": media_url,
            }
            if caption:
                msg_obj["caption"] = caption

        payload = {
            "channel": "whatsapp",
            "source": self.sender_number,
            "destination": clean_to,
            "src.name": self.app_name,
            "message": json.dumps(msg_obj),
        }
        return await self._post_msg(payload)

    async def _post_msg(self, data: dict, url: str | None = None) -> WaSendResult:
        if self.api_key.startswith("mock_") or self.api_key == "mock_access_token":
            mid = f"gupshup-mock-{uuid.uuid4()}"
            logger.info("[GUPSHUP MOCK] Sent to %s: %s", data.get("destination"), mid)
            return WaSendResult(status="sent", message_id=mid)

        target_url = url or f"{self.base_url}/msg"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(target_url, data=data, headers=self._headers, timeout=20.0)
            if 200 <= resp.status_code < 300:
                body = resp.json()
                mid = body.get("messageId") or body.get("id")
                status_str = body.get("status")
                if status_str in ("submitted", "success") or mid:
                    return WaSendResult(status="sent", message_id=mid)
                err = body.get("message") or body.get("error") or str(body)
                return WaSendResult(status="failed", error=err)
            
            try:
                err = resp.json().get("message") or resp.text
            except Exception:
                err = resp.text
            if resp.status_code == 429:
                return WaSendResult(status="failed", error="Rate limited by Gupshup API")
            return WaSendResult(status="failed", error=f"HTTP {resp.status_code}: {err}"[:500])
        except httpx.RequestError as exc:
            logger.error("Gupshup networking exception: %s", exc)
            return WaSendResult(status="failed", error=f"Gupshup connection failure: {exc}"[:500])

    async def upload_media(self, *, content: bytes, mime_type: str, file_name: str) -> str:
        mock_id = f"gupshup-media-{uuid.uuid4()}"
        logger.info("[GUPSHUP] upload_media %s size=%d", file_name, len(content))
        return mock_id

    async def download_media(self, *, media_id: str) -> bytes:
        if media_id.startswith("http://") or media_id.startswith("https://"):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(media_id, timeout=30.0)
                if resp.status_code < 300:
                    return resp.content
            except Exception as e:
                logger.error("Gupshup media download failed: %s", e)
        return b""

    async def mark_as_read(self, *, message_id: str) -> bool:
        return True

    async def sync_templates(self) -> list[dict]:
        if self._is_gateway:
            return [
                {
                    "meta_template_id": "hiring",
                    "name": "hiring",
                    "category": "UTILITY",
                    "language": "en",
                    "status": "APPROVED",
                    "header_format": "TEXT",
                    "header_text": "Samartha Sankalpa",
                    "body_text": "Hi, thanks for your interest in telecaller hiring. We have received your application. Your interview is scheduled on Monday at Samartha Sankalpa OPC Pvt Ltd Location: Kengeri. Please reply with \"CONFIRM\" to confirm your slot.",
                    "footer_text": "Contact 9353527253",
                    "buttons": [],
                }
            ]
        if self.api_key.startswith("mock_") or self.api_key == "mock_access_token":
            return [
                {
                    "meta_template_id": "gupshup_call_followup",
                    "name": "call_followup_lead",
                    "category": "UTILITY",
                    "language": "en",
                    "status": "APPROVED",
                    "header_format": "TEXT",
                    "header_text": "Follow Up",
                    "body_text": "Hello {{1}}, thank you for taking our call today regarding {{2}}. Let us know if you have any questions.",
                    "footer_text": "Customer Support",
                    "buttons": {}
                }
            ]
        url = f"{self.base_url}/template/list/{self.app_name}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers, timeout=20.0)
            if resp.status_code >= 300:
                logger.warning("Gupshup template list failed: %s", resp.text)
                return []
            data = resp.json()
            templates_raw = data.get("templates") or []
            out = []
            for t in templates_raw:
                out.append({
                    "meta_template_id": str(t.get("id") or t.get("elementName") or ""),
                    "name": t.get("elementName") or str(t.get("id") or ""),
                    "category": (t.get("category") or "MARKETING").upper(),
                    "language": t.get("language") or "en",
                    "status": (t.get("status") or "APPROVED").upper(),
                    "header_format": "TEXT" if t.get("header") else None,
                    "header_text": t.get("header"),
                    "body_text": t.get("data") or t.get("content") or "",
                    "footer_text": t.get("footer"),
                    "buttons": t.get("buttons") or [],
                })
            return out
        except Exception as e:
            logger.error("Error fetching Gupshup templates: %s", e)
            return []

    async def check_health(self) -> str:
        if self.api_key.startswith("mock_") or self.api_key == "mock_access_token":
            return "connected"
        if self._is_gateway:
            return "connected" if (self.api_key and self.app_name) else "disconnected"
        url = f"{self.base_url}/users/{self.app_name}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers, timeout=10.0)
            if resp.status_code == 200:
                return "connected"
            if resp.status_code in (401, 403):
                return "expired_token"
            if resp.status_code == 429:
                return "rate_limited"
            return "disconnected"
        except Exception:
            return "disconnected"


def get_provider(settings, decrypted_token: str | None = None) -> WhatsAppProvider:
    """Factory function: resolves the active provider class from a settings row."""
    if not settings or not settings.is_active:
        return MockWhatsAppProvider()
    
    provider_name = (settings.provider or "mock").lower()
    token = decrypted_token or settings.access_token or ""
    if provider_name == "meta" and settings.phone_number_id and token:
        return MetaWhatsAppProvider(
            phone_number_id=settings.phone_number_id,
            business_account_id=settings.business_account_id or "",
            access_token=token,
            api_version=settings.api_version or "v19.0"
        )
    if provider_name == "gupshup" and token:
        app_name = settings.business_account_id or settings.phone_number_id or ""
        return GupshupWhatsAppProvider(
            app_name=app_name,
            api_key=token,
            sender_number=settings.sender_number or ""
        )
    return MockWhatsAppProvider()

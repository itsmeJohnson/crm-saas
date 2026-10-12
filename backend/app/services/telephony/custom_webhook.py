import logging
import httpx
from app.services.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)


class CustomWebhookProvider(TelephonyProvider):
    """Universal Webhook / REST PBX Adapter.
    Allows connecting any third-party telephony provider, PBX, or call center dialer
    (Tata Smartflo, Airtel IQ, Ozonetel, Asterisk, Vicidial, FreePBX, MCube, etc.)
    by providing an outbound API endpoint URL and optional authentication headers.
    """
    name = "custom_webhook"

    async def connect(self) -> dict:
        url = self.config.get("webhook_url")
        if not url:
            return {"success": False, "message": "Missing Outbound Dialer Webhook URL."}
        return {"success": True, "message": "Custom Telephony Webhook configured."}

    async def disconnect(self) -> dict:
        return {"success": True}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        url = self.config.get("webhook_url")
        if not url:
            raise ValueError("Custom Telephony not configured: missing Webhook URL.")

        headers = {"Content-Type": "application/json"}
        token = self.config.get("authentication_token") or self.config.get("x_api_key")
        if token:
            headers["Authorization"] = f"Bearer {token}" if not token.startswith("Basic") else token

        payload = {
            "action": "click_to_call",
            "customer_phone": number,
            "agent_phone": agent_number,
            "caller_id": self.config.get("default_caller_id"),
            "company_id": self.config.get("company_id"),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code in (200, 201, 202):
                    data = {}
                    try:
                        data = res.json()
                    except Exception:
                        pass
                    return {
                        "success": True,
                        "call_id": data.get("call_id") or data.get("id") or "custom-queued",
                        "status": "initiated",
                        "provider": "custom_webhook",
                    }
                else:
                    logger.error("Custom PBX webhook responded with %s: %s", res.status_code, res.text)
                    raise ValueError(f"Custom dialer returned HTTP {res.status_code}: {res.text}")
        except httpx.RequestError as exc:
            logger.error("Connection failed to custom dialer: %s", exc)
            raise ValueError(f"Could not connect to custom dialer webhook: {exc}")

    async def end_call(self, call_id: str) -> dict:
        return {"success": True}

    async def get_users(self) -> list:
        return []

    async def get_call_logs(self, **filters) -> list:
        return []

    async def get_recording(self, call_id: str) -> dict:
        return {"url": None}

from app.services.knowlarity_service import trigger_knowlarity_call
from app.services.telephony.base import TelephonyProvider


class KnowlarityProvider(TelephonyProvider):
    """Knowlarity adapter. Bridges an agent phone to the customer number. The
    agent number is per-user (passed by the dialer), not an org-level secret;
    the org config supplies the API key and caller-id (SRN)."""
    name = "knowlarity"

    async def connect(self) -> dict:
        if not self.config.get("x_api_key"):
            return {"success": False, "message": "Missing Knowlarity API key."}
        return {"success": True, "message": "Knowlarity credentials present."}

    async def disconnect(self) -> dict:
        return {"success": True}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        if not self.config.get("x_api_key"):
            raise ValueError("Knowlarity not configured: missing API key.")
        if not agent_number:
            raise ValueError("Knowlarity requires the agent's phone number.")
        return await trigger_knowlarity_call(
            api_key=self.config["x_api_key"],
            srn=self.config.get("default_caller_id") or "",
            agent_number=agent_number,
            customer_number=number,
        )

    async def end_call(self, call_id: str) -> dict:
        return {"success": True, "message": "Not supported."}

    async def get_users(self) -> list:
        return []

    async def get_call_logs(self, **filters) -> list:
        return []

    async def get_recording(self, call_id: str) -> dict:
        return {"success": False, "message": "Not implemented for Knowlarity."}

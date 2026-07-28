import logging

import httpx

from app.services.myoperator_service import trigger_myoperator_call
from app.services.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)

# Call APIs (logs + recordings): token auth on a different base URL.
MYOPERATOR_DEV_BASE = "https://developers.myoperator.co"

_REQUIRED = ("company_id", "x_api_key", "secret_token", "public_ivr_id")


class MyOperatorProvider(TelephonyProvider):
    """MyOperator adapter. Outbound uses the OBD API (see myoperator_service);
    logs/recordings use the Call APIs with the account's Calling API Token."""
    name = "myoperator"

    def _missing(self) -> list[str]:
        return [f for f in _REQUIRED if not self.config.get(f)]

    async def connect(self) -> dict:
        missing = self._missing()
        if missing:
            return {"success": False, "message": f"Missing MyOperator fields: {', '.join(missing)}"}
        return {"success": True, "message": "MyOperator credentials present."}

    async def disconnect(self) -> dict:
        return {"success": True}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        missing = self._missing()
        if missing:
            raise ValueError(f"MyOperator not configured: missing {', '.join(missing)}")
        return await trigger_myoperator_call(
            x_api_key=self.config["x_api_key"],
            secret_key=self.config["secret_token"],
            company_id=self.config["company_id"],
            number=number,
            public_ivr_id=self.config["public_ivr_id"],
            call_type=self.config.get("call_type") or "1",
        )

    async def end_call(self, call_id: str) -> dict:
        # MyOperator OBD calls are not hung up via API in this integration.
        return {"success": True, "message": "Not supported by MyOperator OBD."}

    def _token(self) -> str | None:
        # Call APIs use the "Calling API Token" == the Authentication token.
        return self.config.get("authentication_token") or self.config.get("secret_token")

    async def get_users(self) -> list:
        token = self._token()
        if not token:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{MYOPERATOR_DEV_BASE}/users", params={"token": token}, timeout=12.0)
            if r.status_code >= 300:
                logger.warning("MyOperator get_users failed: %s %s", r.status_code, r.text)
                return []
            data = r.json()
            return data.get("data") or data.get("users") or []

    async def get_call_logs(self, **filters) -> list:
        token = self._token()
        if not token:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{MYOPERATOR_DEV_BASE}/logs/search",
                                  json={"token": token, **filters}, timeout=15.0)
            if r.status_code >= 300:
                logger.warning("MyOperator get_call_logs failed: %s %s", r.status_code, r.text)
                return []
            data = r.json()
            return data.get("data") or []

    async def get_recording(self, call_id: str) -> dict:
        token = self._token()
        if not token:
            return {"success": False, "message": "No token configured."}
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{MYOPERATOR_DEV_BASE}/recording",
                                 params={"token": token, "call_id": call_id}, timeout=12.0)
            if r.status_code >= 300:
                return {"success": False, "message": r.text}
            return {"success": True, **r.json()}

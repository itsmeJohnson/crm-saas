import logging
import httpx
from app.services.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)

# Exotel API base pattern: https://<api_key>:<api_token>@api.exotel.com/v1/Accounts/<account_sid>/Calls/connect.json
_REQUIRED = ("company_id", "x_api_key", "secret_token")  # company_id = AccountSid, x_api_key = API Key, secret_token = API Token
_REQUIRED_OUTBOUND = ("company_id", "x_api_key", "secret_token", "default_caller_id")


class ExotelProvider(TelephonyProvider):
    """Exotel Cloud Telephony Provider.
    Bridges agent phone to customer phone via Exotel Connect API.
    """
    name = "exotel"

    def _missing(self, required=_REQUIRED) -> list[str]:
        return [f for f in required if not self.config.get(f)]

    async def connect(self) -> dict:
        missing = self._missing()
        if missing:
            return {"success": False, "message": f"Missing Exotel credentials: {', '.join(missing)}"}
        return {"success": True, "message": "Exotel credentials configured successfully."}

    async def disconnect(self) -> dict:
        return {"success": True}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        missing = self._missing(_REQUIRED_OUTBOUND)
        if missing:
            raise ValueError(f"Exotel outbound not configured: missing {', '.join(missing)}")
        if not agent_number:
            raise ValueError("Exotel requires an agent phone number to bridge the call.")

        account_sid = self.config["company_id"].strip()
        api_key = self.config["x_api_key"].strip()
        api_token = self.config["secret_token"].strip()
        caller_id = self.config["default_caller_id"].strip()

        clean_customer = number.replace("+", "").strip()
        clean_agent = agent_number.replace("+", "").strip()

        url = f"https://api.exotel.com/v1/Accounts/{account_sid}/Calls/connect.json"

        payload = {
            "From": clean_agent,
            "To": clean_customer,
            "CallerId": caller_id,
            "CallType": "trans",
            "TimeLimit": self.config.get("max_call_duration_seconds", 3600),
        }
        if self.config.get("webhook_url"):
            payload["StatusCallback"] = self.config["webhook_url"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, data=payload, auth=(api_key, api_token))
                if res.status_code in (200, 201):
                    data = res.json()
                    call = data.get("Call", {})
                    return {
                        "success": True,
                        "call_id": call.get("Sid"),
                        "status": call.get("Status", "queued"),
                        "provider": "exotel",
                    }
                else:
                    logger.error("Exotel call initiation failed [%s]: %s", res.status_code, res.text)
                    raise ValueError(f"Exotel API error ({res.status_code}): {res.text}")
        except httpx.RequestError as exc:
            logger.error("Exotel network request error: %s", exc)
            raise ValueError(f"Could not connect to Exotel servers: {exc}")

    async def end_call(self, call_id: str) -> dict:
        return {"success": True, "message": "Hangup managed by Exotel leg completion."}

    async def get_users(self) -> list:
        return []

    async def get_call_logs(self, **filters) -> list:
        return []

    async def get_recording(self, call_id: str) -> dict:
        account_sid = self.config.get("company_id", "").strip()
        api_key = self.config.get("x_api_key", "").strip()
        api_token = self.config.get("secret_token", "").strip()
        if not (account_sid and api_key and api_token and call_id):
            return {"url": None}

        url = f"https://api.exotel.com/v1/Accounts/{account_sid}/Calls/{call_id}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, auth=(api_key, api_token))
                if res.status_code == 200:
                    call = res.json().get("Call", {})
                    return {"url": call.get("RecordingUrl")}
        except Exception as e:
            logger.warning("Could not fetch Exotel recording: %s", e)
        return {"url": None}

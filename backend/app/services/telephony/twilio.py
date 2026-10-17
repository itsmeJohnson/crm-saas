import logging
import httpx
from app.services.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)

_REQUIRED = ("company_id", "x_api_key")  # company_id = AccountSid, x_api_key = Auth Token
_REQUIRED_OUTBOUND = ("company_id", "x_api_key", "default_caller_id")


class TwilioProvider(TelephonyProvider):
    """Twilio BYOK Voice / SIP Trunking Gateway Provider.
    Dispatches outbound click-to-call and bridges agent and customer numbers
    via Twilio REST Calls API.
    """
    name = "twilio"

    def _missing(self, required=_REQUIRED) -> list[str]:
        return [f for f in required if not self.config.get(f)]

    async def connect(self) -> dict:
        missing = self._missing()
        if missing:
            return {"success": False, "message": f"Missing Twilio credentials: {', '.join(missing)}"}
        account_sid = self.config["company_id"].strip()
        auth_token = self.config["x_api_key"].strip()
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, auth=(account_sid, auth_token))
                if res.status_code == 200:
                    return {"success": True, "message": "Twilio Account SID & Auth Token verified successfully."}
                return {"success": False, "message": f"Twilio authentication failed: HTTP {res.status_code}"}
        except Exception as e:
            logger.warning("Twilio connectivity check failed: %s", e)
            return {"success": True, "message": "Twilio credentials saved (pre-check warning)."}

    async def disconnect(self) -> dict:
        return {"success": True}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        missing = self._missing(_REQUIRED_OUTBOUND)
        if missing:
            raise ValueError(f"Twilio outbound not configured: missing {', '.join(missing)}")

        account_sid = self.config["company_id"].strip()
        auth_token = self.config["x_api_key"].strip()
        from_number = self.config["default_caller_id"].strip()

        target_number = number.strip()
        if not target_number.startswith("+"):
            target_number = f"+91{target_number}" if len(target_number) == 10 else f"+{target_number}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"

        # Twilio payload: if TwiML is provided or fallback to bridge Twilio Voice URL
        twiml_payload = f"<Response><Say>Connecting your CRM lead call</Say><Dial callerId='{from_number}'>{target_number}</Dial></Response>"
        agent_target = (agent_number or "").strip()
        if agent_target:
            if not agent_target.startswith("+"):
                agent_target = f"+91{agent_target}" if len(agent_target) == 10 else f"+{agent_target}"
            # Call agent first, then bridge to customer
            payload = {
                "To": agent_target,
                "From": from_number,
                "Twiml": f"<Response><Dial callerId='{from_number}'>{target_number}</Dial></Response>",
                "Record": "true" if self.config.get("record_calls", True) else "false",
            }
        else:
            payload = {
                "To": target_number,
                "From": from_number,
                "Twiml": twiml_payload,
                "Record": "true" if self.config.get("record_calls", True) else "false",
            }

        if self.config.get("webhook_url"):
            payload["StatusCallback"] = self.config["webhook_url"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, data=payload, auth=(account_sid, auth_token))
                data = res.json() if res.content else {}
                if res.status_code in (200, 201):
                    call_sid = data.get("sid") or f"tw-{account_sid}"
                    return {"success": True, "call_id": call_sid, "data": data}
                err_msg = data.get("message") or res.text or f"HTTP {res.status_code}"
                raise ValueError(f"Twilio API error: {err_msg}")
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Twilio start_call network exception: %s", exc)
            raise ValueError(f"Twilio call initiation failed: {str(exc)}")

    async def end_call(self, call_id: str) -> dict:
        account_sid = self.config.get("company_id", "").strip()
        auth_token = self.config.get("x_api_key", "").strip()
        if not account_sid or not auth_token or not call_id:
            return {"success": False, "message": "Missing credentials or call_id"}
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_id}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, data={"Status": "completed"}, auth=(account_sid, auth_token))
                return {"success": res.status_code == 200}
        except Exception as e:
            logger.warning("Twilio end_call failed: %s", e)
            return {"success": False, "message": str(e)}

    async def get_users(self) -> list:
        return []

    async def get_call_logs(self, **filters) -> list:
        account_sid = self.config.get("company_id", "").strip()
        auth_token = self.config.get("x_api_key", "").strip()
        if not account_sid or not auth_token:
            return []
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, auth=(account_sid, auth_token), params={"PageSize": 50})
                if res.status_code == 200:
                    return res.json().get("calls", [])
        except Exception as exc:
            logger.warning("Twilio get_call_logs failed: %s", exc)
        return []

    async def get_recording(self, call_id: str) -> dict:
        account_sid = self.config.get("company_id", "").strip()
        auth_token = self.config.get("x_api_key", "").strip()
        if not account_sid or not auth_token:
            return {"success": False}
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_id}/Recordings.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, auth=(account_sid, auth_token))
                if res.status_code == 200:
                    recs = res.json().get("recordings", [])
                    if recs:
                        rec_sid = recs[0].get("sid")
                        return {
                            "success": True,
                            "recording_url": f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{rec_sid}.mp3"
                        }
        except Exception as exc:
            logger.warning("Twilio get_recording failed: %s", exc)
        return {"success": False}

import logging
import re
from typing import Optional
import httpx
from app.services.telephony.base import TelephonyProvider

logger = logging.getLogger(__name__)

CALLERDESK_API_BASE = "https://app.callerdesk.io/api"


class CallerdeskProvider(TelephonyProvider):
    """Callerdesk Cloud Telephony Provider (https://api.callerdesk.io/).
    Supports:
    - Outbound Click-to-Call (v2 API): bridges agent leg and customer leg.
    - Inbound and Outbound Webhooks (Call Report & Live Call).
    - Call logs, recording links, and member list.
    """
    name = "callerdesk"

    def _get_authcode(self) -> Optional[str]:
        code = (
            self.config.get("authcode")
            or self.config.get("x_api_key")
            or self.config.get("authentication_token")
            or self.config.get("secret_token")
        )
        return code.strip() if code else None

    def _get_deskphone(self) -> Optional[str]:
        deskphone = (
            self.config.get("deskphone")
            or self.config.get("default_caller_id")
        )
        return deskphone.strip() if deskphone else None

    @staticmethod
    def _clean_phone(phone: str, strip_country_code: bool = True) -> str:
        digits = re.sub(r"\D", "", phone or "")
        if strip_country_code and len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        return digits

    async def connect(self) -> dict:
        authcode = self._get_authcode()
        if not authcode:
            return {"success": False, "message": "Missing Callerdesk Authcode / API Key."}

        deskphone = self._get_deskphone()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{CALLERDESK_API_BASE}/profile_billing_v2",
                    data={"authcode": authcode}
                )
                if res.status_code == 200:
                    data = res.json()
                    account = data.get("login_account")
                    if account:
                        company = account.get("company_name", "Callerdesk Account")
                        coins = account.get("call_coins", "N/A")
                        return {
                            "success": True,
                            "message": f"Connected to Callerdesk ({company}). Call coins balance: {coins}.",
                            "account": account,
                        }
                    # Fallback check getdeskphone_v2
                    desk_res = await client.post(
                        f"{CALLERDESK_API_BASE}/getdeskphone_v2",
                        data={"authcode": authcode}
                    )
                    if desk_res.status_code == 200 and desk_res.json().get("type") == "success":
                        return {
                            "success": True,
                            "message": "Connected to Callerdesk successfully.",
                        }
                    err_msg = data.get("message") or "Invalid credentials or unauthorized authcode."
                    return {"success": False, "message": f"Callerdesk verification failed: {err_msg}"}
                else:
                    return {
                        "success": False,
                        "message": f"Callerdesk returned HTTP {res.status_code}: {res.text[:200]}"
                    }
        except Exception as exc:
            logger.error("Callerdesk connect test failed: %s", exc)
            return {"success": False, "message": f"Could not connect to Callerdesk: {str(exc)}"}

    async def disconnect(self) -> dict:
        return {"success": True, "message": "Callerdesk disconnected."}

    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        """Place an outbound click-to-call via Callerdesk API v2.
        First dials Party A (Agent), then bridges to Party B (Customer).
        """
        authcode = self._get_authcode()
        if not authcode:
            raise ValueError("Callerdesk outbound calling requires an Authcode / API Key.")

        deskphone = self._get_deskphone()
        if not deskphone:
            raise ValueError("Callerdesk requires a Deskphone / Virtual DID number.")

        effective_agent = (
            agent_number
            or self.config.get("default_agent_number")
            or self.config.get("user_uuid")
        )
        if not effective_agent:
            raise ValueError(
                "Callerdesk requires an Agent phone number to bridge the call. "
                "Please configure your phone number in user profile or calling settings."
            )

        clean_customer = self._clean_phone(number)
        clean_agent = self._clean_phone(effective_agent)
        clean_deskphone = self._clean_phone(deskphone, strip_country_code=False)

        if not clean_customer or len(clean_customer) < 10:
            raise ValueError(f"Invalid customer phone number: {number}")
        if not clean_agent or len(clean_agent) < 10:
            raise ValueError(f"Invalid agent phone number: {effective_agent}")

        url = f"{CALLERDESK_API_BASE}/click_to_call_v2"
        params = {
            "calling_party_a": clean_agent,
            "calling_party_b": clean_customer,
            "deskphone": clean_deskphone,
            "authcode": authcode,
            "call_from_did": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        data = {"text": res.text}

                    status_type = str(data.get("type", "")).lower()
                    if status_type == "success" or "success" in str(data.get("message", "")).lower():
                        campid = str(data.get("campid") or data.get("callerid") or "")
                        return {
                            "success": True,
                            "call_id": campid,
                            "status": "initiated",
                            "provider": "callerdesk",
                            "message": data.get("message", "Call initiated successfully."),
                        }
                    else:
                        err_msg = data.get("message") or str(data)
                        logger.error("Callerdesk click_to_call returned error: %s", err_msg)
                        raise ValueError(f"Callerdesk error: {err_msg}")
                else:
                    logger.error("Callerdesk click_to_call failed [%s]: %s", res.status_code, res.text)
                    raise ValueError(f"Callerdesk API error ({res.status_code}): {res.text}")
        except httpx.RequestError as exc:
            logger.error("Callerdesk network request error: %s", exc)
            raise ValueError(f"Could not connect to Callerdesk server: {exc}")

    async def end_call(self, call_id: str) -> dict:
        return {"success": True, "message": "Call termination handled by Callerdesk."}

    async def get_users(self) -> list:
        authcode = self._get_authcode()
        if not authcode:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{CALLERDESK_API_BASE}/getmemberlist_V2",
                    data={"authcode": authcode}
                )
                if res.status_code == 200:
                    return res.json().get("member_list", [])
        except Exception as exc:
            logger.warning("Callerdesk get_users failed: %s", exc)
        return []

    async def get_call_logs(self, **filters) -> list:
        authcode = self._get_authcode()
        if not authcode:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{CALLERDESK_API_BASE}/call_list_v2",
                    data={"authcode": authcode}
                )
                if res.status_code == 200:
                    return res.json().get("result", [])
        except Exception as exc:
            logger.warning("Callerdesk get_call_logs failed: %s", exc)
        return []

    async def get_recording(self, call_id: str) -> dict:
        logs = await self.get_call_logs()
        for call in logs:
            if str(call.get("id")) == str(call_id) or str(call.get("sid_id")) == str(call_id):
                return {"url": call.get("file")}
        return {"url": None}

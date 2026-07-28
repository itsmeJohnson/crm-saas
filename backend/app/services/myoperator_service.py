import logging
import httpx

logger = logging.getLogger(__name__)

# OBD (Outbound Dialing / click-to-call) endpoint.
# Panel: API & Webhook → Calling APIs → Endpoint Details.
MYOPERATOR_OBD_URL = "https://obd-api.myoperator.co/obd-api-v1"


async def trigger_myoperator_call(
    x_api_key: str,
    secret_key: str,
    company_id: str,
    number: str,
    public_ivr_id: str,
    call_type: str = "1",
):
    """
    Trigger a MyOperator OBD (outbound dialing / click-to-call) request.

    Auth (MyOperator panel → Calling APIs → Endpoint Details):
        headers: x-api-key, secret-key
        base URL: https://obd-api.myoperator.co/obd-api-v1

    Body schema is fixed by MyOperator (discovered from the API's own validation):
        company_id     — MyOperator Company ID
        number         — the number to dial (the lead's phone)
        public_ivr_id  — the outbound Public IVR / call flow that routes the call
                         (configured in the MyOperator panel; not in Endpoint Details)
        secret_token   — the "Authentication" secret (same value as the secret-key)
        type           — OBD call type, one of "1" | "2" | "3"

    `number` is what MyOperator dials; the agent leg is defined by the Public IVR
    flow on MyOperator's side, so no agent number is sent here.
    """
    headers = {
        "x-api-key": x_api_key.strip(),
        "secret-key": secret_key.strip(),
        "Content-Type": "application/json",
    }

    payload = {
        "company_id": company_id.strip(),
        "number": number.strip(),
        "public_ivr_id": str(public_ivr_id).strip(),
        "secret_token": secret_key.strip(),
        "type": str(call_type or "1").strip(),
    }

    logger.info(
        "Initiating MyOperator OBD call: number=%s public_ivr_id=%s type=%s company=%s",
        number, public_ivr_id, payload["type"], company_id,
    )

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(MYOPERATOR_OBD_URL, json=payload, headers=headers, timeout=15.0)
            logger.info("MyOperator OBD response: status=%s body=%s", resp.status_code, resp.text)
            if resp.status_code < 200 or resp.status_code >= 300:
                raise ValueError(f"MyOperator OBD API responded {resp.status_code}: {resp.text}")
            return resp.json()
        except httpx.RequestError as exc:
            logger.error("HTTP connection error to MyOperator OBD API: %s", exc)
            raise ValueError(f"Unable to connect to MyOperator telephony server: {exc}")

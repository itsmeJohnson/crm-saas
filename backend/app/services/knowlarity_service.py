import logging
import httpx

logger = logging.getLogger(__name__)

async def trigger_knowlarity_call(api_key: str, srn: str, agent_number: str, customer_number: str):
    """
    Triggers Knowlarity outbound Click-to-Call API to connect agent and customer.
    Knowlarity makecall endpoint: https://api.knowlarity.com/v1/call/makecall
    """
    url = "https://api.knowlarity.com/v1/call/makecall"
    
    # Clean phone numbers (strip spaces and ensure basic prefix format if needed)
    agent_clean = agent_number.strip()
    customer_clean = customer_number.strip()
    
    headers = {
        "Authorization": api_key,
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "agent_number": agent_clean,
        "customer_number": customer_clean,
        "caller_id": srn.strip() if srn else ""
    }
    
    logger.info(f"Initiating Click-to-Call via Knowlarity: Agent {agent_clean} -> Customer {customer_clean}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=12.0)
            logger.info(f"Knowlarity outbound response: status={response.status_code}, response={response.text}")
            
            # Raise exception if status is non-2xx
            if response.status_code < 200 or response.status_code >= 300:
                raise ValueError(f"Knowlarity API responded with status {response.status_code}: {response.text}")
                
            return response.json()
        except httpx.RequestError as exc:
            logger.error(f"HTTP connection error to Knowlarity API: {str(exc)}")
            raise ValueError(f"Unable to connect to Knowlarity telephony server: {str(exc)}")
        except Exception as exc:
            logger.error(f"Failed to trigger Knowlarity call: {str(exc)}")
            raise exc

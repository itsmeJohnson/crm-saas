from app.services.telephony.base import TelephonyProvider
from app.services.telephony.knowlarity import KnowlarityProvider
from app.services.telephony.myoperator import MyOperatorProvider
from app.services.telephony.exotel import ExotelProvider
from app.services.telephony.callerdesk import CallerdeskProvider
from app.services.telephony.twilio import TwilioProvider
from app.services.telephony.msg91 import Msg91Provider
from app.services.telephony.custom_webhook import CustomWebhookProvider
from app.services.telephony.telecmi import TeleCMIProvider

_PROVIDERS = {
    "myoperator": MyOperatorProvider,
    "knowlarity": KnowlarityProvider,
    "exotel": ExotelProvider,
    "callerdesk": CallerdeskProvider,
    "telecmi": TeleCMIProvider,
    "twilio": TwilioProvider,
    "msg91": Msg91Provider,
    "custom_webhook": CustomWebhookProvider,
    "tata_smartflo": CustomWebhookProvider,
    "airtel_iq": CustomWebhookProvider,
    "ozonetel": CustomWebhookProvider,
}


def get_provider(config: dict) -> TelephonyProvider:
    """Instantiate the provider named by ``config['provider']`` (default
    myoperator). Raises ValueError for an unknown provider."""
    name = (config or {}).get("provider") or "myoperator"
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unsupported telephony provider: {name}")
    return cls(config)

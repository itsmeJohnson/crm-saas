from app.services.telephony.base import TelephonyProvider
from app.services.telephony.knowlarity import KnowlarityProvider
from app.services.telephony.myoperator import MyOperatorProvider

_PROVIDERS = {
    "myoperator": MyOperatorProvider,
    "knowlarity": KnowlarityProvider,
}


def get_provider(config: dict) -> TelephonyProvider:
    """Instantiate the provider named by ``config['provider']`` (default
    myoperator). Raises ValueError for an unknown provider."""
    name = (config or {}).get("provider") or "myoperator"
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unsupported telephony provider: {name}")
    return cls(config)

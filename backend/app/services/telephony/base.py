"""Provider abstraction for telephony/calling gateways.

CRM business logic (dialer, call logging) depends only on this interface, never
on a concrete provider. New providers (Exotel, Twilio, MSG91, Gupshup, …) drop in
by implementing ``TelephonyProvider`` and registering in ``factory.get_provider``.

Every provider is constructed from a decrypted org config dict
(``TelephonyConfigService.get_decrypted_config``) — the only place credentials
are ever in plaintext, and always server-side.
"""
from abc import ABC, abstractmethod


class TelephonyProvider(ABC):
    name: str = "base"

    def __init__(self, config: dict):
        self.config = config or {}

    @abstractmethod
    async def connect(self) -> dict:
        """Validate credentials / reachability. -> {success: bool, message: str}."""

    @abstractmethod
    async def disconnect(self) -> dict:
        """Tear down any provider-side session. -> {success: bool}."""

    @abstractmethod
    async def start_call(self, *, number: str, agent_number: str | None = None) -> dict:
        """Place an outbound (click-to-call) call. -> provider response dict."""

    @abstractmethod
    async def end_call(self, call_id: str) -> dict:
        """End / hang up an in-progress call."""

    @abstractmethod
    async def get_users(self) -> list:
        """List provider-side agents/users."""

    @abstractmethod
    async def get_call_logs(self, **filters) -> list:
        """Fetch call logs from the provider."""

    @abstractmethod
    async def get_recording(self, call_id: str) -> dict:
        """Fetch a recording link for a call."""

    async def send_webhook(self, payload: dict) -> dict:
        """Handle an inbound webhook payload from the provider. Default: no-op ack."""
        return {"success": True}

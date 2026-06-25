import uuid
from pydantic import BaseModel
from datetime import datetime


class PaymentGatewayCreate(BaseModel):
    name: str
    display_name: str
    is_enabled: bool = False
    is_sandbox: bool = True
    api_key: str | None = None
    api_secret: str | None = None
    webhook_secret: str | None = None
    extra_config: dict | None = None
    sort_order: int = 0
    description: str | None = None


class PaymentGatewayUpdate(BaseModel):
    display_name: str | None = None
    is_enabled: bool | None = None
    is_sandbox: bool | None = None
    api_key: str | None = None
    api_secret: str | None = None
    webhook_secret: str | None = None
    extra_config: dict | None = None
    sort_order: int | None = None
    description: str | None = None


class PaymentGatewayResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    is_enabled: bool
    is_sandbox: bool
    # Never return api_secret in response
    api_key_set: bool = False
    webhook_secret_set: bool = False
    sort_order: int
    description: str | None = None
    extra_config: dict | None = None
    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, gw) -> "PaymentGatewayResponse":
        return cls(
            id=gw.id,
            name=gw.name,
            display_name=gw.display_name,
            is_enabled=gw.is_enabled,
            is_sandbox=gw.is_sandbox,
            api_key_set=bool(gw.api_key),
            webhook_secret_set=bool(gw.webhook_secret),
            sort_order=gw.sort_order,
            description=gw.description,
            extra_config=gw.extra_config
        )

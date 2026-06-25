from pydantic import BaseModel
from datetime import datetime


class CurrencyCreate(BaseModel):
    code: str
    name: str
    symbol: str
    exchange_rate: float = 1.0
    is_base: bool = False
    is_active: bool = True
    source: str = "manual"


class CurrencyUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    exchange_rate: float | None = None
    is_active: bool | None = None
    is_base: bool | None = None
    source: str | None = None


class CurrencyResponse(BaseModel):
    code: str
    name: str
    symbol: str
    exchange_rate: float
    is_base: bool
    is_active: bool
    source: str
    last_updated: datetime | None = None
    model_config = {"from_attributes": True}

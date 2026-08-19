import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductCatalogCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: str | None = Field(None, max_length=100)
    code: str | None = Field(None, max_length=40)
    price: Decimal = Field(0, ge=0)
    tax_percent: Decimal = Field(0, ge=0, le=100)
    duration_minutes: int | None = Field(None, ge=0)
    description: str | None = None
    is_active: bool = True


class ProductCatalogUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=100)
    code: str | None = Field(None, max_length=40)
    price: Decimal | None = Field(None, ge=0)
    tax_percent: Decimal | None = Field(None, ge=0, le=100)
    duration_minutes: int | None = Field(None, ge=0)
    description: str | None = None
    is_active: bool | None = None


class ProductCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    category: str | None = None
    code: str | None = None
    price: Decimal
    tax_percent: Decimal
    duration_minutes: int | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime

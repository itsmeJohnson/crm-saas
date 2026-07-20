import uuid
from pydantic import BaseModel, field_validator
from datetime import datetime


class CouponCreate(BaseModel):
    code: str
    description: str | None = None
    discount_type: str = "percentage"  # percentage, flat
    discount_value: float
    max_uses: int | None = None
    valid_from: datetime
    valid_until: datetime | None = None
    min_order_value: float = 0.0
    applicable_plans: list[str] | None = None
    is_active: bool = True
    notes: str | None = None

    @field_validator("discount_value")
    @classmethod
    def validate_discount(cls, v, info):
        if v < 0:
            raise ValueError("Discount value must be positive")
        return v


class CouponUpdate(BaseModel):
    description: str | None = None
    discount_value: float | None = None
    max_uses: int | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None
    notes: str | None = None


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str | None = None
    discount_type: str
    discount_value: float
    max_uses: int | None = None
    uses_count: int
    valid_from: datetime
    valid_until: datetime | None = None
    min_order_value: float
    applicable_plans: list | None = None
    is_active: bool
    notes: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

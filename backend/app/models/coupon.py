import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, Integer, Boolean, JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Coupon(BaseModel):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(20), default="percentage", nullable=False)  # percentage, flat
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    min_order_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    applicable_plans: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

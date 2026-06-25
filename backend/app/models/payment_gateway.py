from sqlalchemy import String, Boolean, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class PaymentGateway(BaseModel):
    __tablename__ = "payment_gateways"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

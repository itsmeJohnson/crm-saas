from sqlalchemy import String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class TaxConfig(BaseModel):
    __tablename__ = "tax_configs"

    country_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(20), nullable=False, default="GST")  # GST, VAT, SALES_TAX, NONE
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    tax_label: Mapped[str] = mapped_column(String(50), nullable=False, default="Tax")
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

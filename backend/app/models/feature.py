from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Feature(BaseModel):
    __tablename__ = "features"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # "Calls", "Leads", "Analytics", etc.
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Lucide icon name
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

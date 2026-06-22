from sqlalchemy import String, Numeric, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class Plan(BaseModel):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    price_inr: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    billing_cycle_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_admins: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_managers: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_team_leads: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_employees: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

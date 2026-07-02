import uuid
from sqlalchemy import ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class EscalationConfig(BaseModel):
    """Per-organization configuration for automatic lead escalation.

    A lead is escalated when it has had no activity for `idle_days` days; the
    lead owner's manager (reporting_to) is notified. Singleton per org, mirrors
    the AssignmentConfig pattern.
    """
    __tablename__ = "escalation_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idle_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

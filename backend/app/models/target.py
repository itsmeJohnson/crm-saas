import uuid
import enum
from datetime import date
from sqlalchemy import ForeignKey, Enum, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class TargetType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

class MetricType(str, enum.Enum):
    CALLS_MADE = "CALLS_MADE"
    LEADS_CONVERTED = "LEADS_CONVERTED"

class PerformanceTarget(BaseModel):
    __tablename__ = "performance_targets"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType, native_enum=False), nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType, native_enum=False), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")

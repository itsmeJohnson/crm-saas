import uuid
from sqlalchemy import ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class PlanFeature(BaseModel):
    __tablename__ = "plan_features"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="plan_features")
    feature: Mapped["Feature"] = relationship("Feature")

import uuid
from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class WorkflowRule(BaseModel):
    """A bounded lead-automation rule: when `trigger_event` fires and all
    `conditions` match, run `actions` in order.

    trigger_event: "lead_created" | "lead_updated"
    conditions: list of {"field": str, "op": str, "value": Any}
    actions:    list of {"type": str, ...params}
    """
    __tablename__ = "workflow_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

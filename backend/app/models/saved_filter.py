import uuid
from sqlalchemy import String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SavedFilter(BaseModel):
    __tablename__ = "saved_filters"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), default="lead", nullable=False, index=True)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)  # serialized filter params
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # visible org-wide

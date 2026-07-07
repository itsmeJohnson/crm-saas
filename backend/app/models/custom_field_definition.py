import uuid
from sqlalchemy import String, ForeignKey, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class CustomFieldDefinition(BaseModel):
    """Org-level definition of a custom field for an entity (contacts today).

    The actual values live in the entity's `custom_fields` JSON column keyed by
    `key`; this table describes the label/type so the UI can render + validate.
    """
    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "entity_type", "key", name="uq_custom_field_org_entity_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), default="contact", nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)  # stable machine key
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), default="text", nullable=False)  # text|number|date|select|checkbox
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # choices for select
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

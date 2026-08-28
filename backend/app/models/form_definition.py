import uuid
from sqlalchemy import String, ForeignKey, JSON, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class FormDefinition(BaseModel):
    """A tenant-defined FORM (layout) for an entity (Phase 7 — Dynamic Forms).

    A form does NOT define fields (those live in CustomFieldDefinition) and does
    NOT store values (those live in the entity's custom_fields / record.data).
    It stores a LAYOUT: which fields, in what order, grouped into sections, with
    per-form presentation overrides (required / hidden / read_only).

    Belongs to CRM Core (the Configuration Engine) — no industry coupling.

    ``schema`` shape::

        {"sections": [
            {"title": "Basics", "columns": 2, "fields": [
                {"key": "budget", "required": true},
                {"key": "property_type", "hidden": false, "read_only": false}
            ]}
        ]}
    """
    __tablename__ = "form_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", "key", name="uq_form_org_entity_key"),
        Index("ix_form_definitions_org_entity_active", "organization_id", "entity_type", "is_active"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # lead|contact|<object key>
    key: Mapped[str] = mapped_column(String(80), nullable=False)  # stable machine key, unique per org+entity
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {sections:[{title,columns,fields:[{key,...}]}]}

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

import uuid
from sqlalchemy import String, ForeignKey, JSON, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class CustomObjectDefinition(BaseModel):
    """A tenant-defined object type (e.g. Property, Policy, Loan).

    Its *fields* are ordinary ``CustomFieldDefinition`` rows with
    ``entity_type == this.key`` — the SAME engine that powers Lead/Contact
    custom fields. Its *records* live in ``custom_object_records.data`` (JSON).
    Belongs to CRM Core (the Configuration Engine) — no industry coupling.
    """
    __tablename__ = "custom_object_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_custom_object_org_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(50), nullable=False)  # machine key, unique per org
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    label_plural: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Which field key renders as a record's title in lists/pickers.
    display_field_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    records: Mapped[list["CustomObjectRecord"]] = relationship(
        "CustomObjectRecord", back_populates="object_definition"
    )


class CustomObjectRecord(BaseModel):
    """A single record of a custom object. Values live in the generic ``data``
    JSON column keyed by field_key — the same definition/value separation used
    by ``Lead.custom_fields`` / ``Contact.custom_fields``.

    One shared table for ALL objects (never a physical table per tenant-object).
    """
    __tablename__ = "custom_object_records"
    __table_args__ = (
        Index("ix_custom_object_records_org_obj_deleted", "organization_id", "object_definition_id", "is_deleted"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    object_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_object_definitions.id"), nullable=False, index=True
    )
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {field_key: value}

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    object_definition: Mapped["CustomObjectDefinition"] = relationship(
        "CustomObjectDefinition", back_populates="records"
    )

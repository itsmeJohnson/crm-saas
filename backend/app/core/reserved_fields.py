"""Central registry of reserved custom-field keys and supported entity types.

A tenant custom field must never shadow a first-class / system-controlled column
of a Core entity (a custom field keyed ``email`` would silently diverge from the
real ``email`` column). Rather than scatter these checks, every rule lives here.

Belongs to CRM Core — imports no industry modules.
"""
from __future__ import annotations

# Phase 4.1 supports custom fields only on entities that already own a
# ``custom_fields`` JSON column: Lead and Contact. Anything else is rejected
# (G4) until a later phase adds storage for it.
SUPPORTED_ENTITY_TYPES: set[str] = {"lead", "contact"}

# Columns from app.models.base.BaseModel plus generic system-controlled names.
_BASE_RESERVED: set[str] = {
    "id",
    "organization_id",
    "created_at",
    "updated_at",
    "deleted_at",
    "is_deleted",
    "created_by",
    "updated_by",
    "custom_fields",
    "attachments",
    "owner_id",  # defensive: not a column today, but a conventional system key
    "name",      # defensive: composed display name, not a raw column
}

# Real first-class columns on app.models.lead.Lead.
_LEAD_RESERVED: set[str] = _BASE_RESERVED | {
    "first_name",
    "last_name",
    "city",
    "email",
    "phone",
    "company_name",
    "company_id",
    "title",
    "status",
    "lost_reason",
    "source",
    "value",
    "priority",
    "score",
    "assigned_user_id",
    "import_id",
    "pipeline_id",
    "stage_id",
    "available_at",
    "call_attempts_count",
    "is_archived",
    "archived_at",
    "converted_contact_id",
    "converted_at",
    "pin_code",
    "branch_id",
    "territory_id",
    "tags",
}

# Real first-class columns on app.models.contact.Contact.
_CONTACT_RESERVED: set[str] = _BASE_RESERVED | {
    "first_name",
    "last_name",
    "email",
    "phone",
    "job_title",
    "company_id",
    "assigned_user_id",
    "tags",
    "status",  # defensive alignment with lead + common consumer expectations
}

RESERVED_KEYS: dict[str, set[str]] = {
    "lead": _LEAD_RESERVED,
    "contact": _CONTACT_RESERVED,
}

# Custom-object records are pure JSON with NO first-class business columns, so
# only the record's actual system columns collide (never "name"/"owner_id",
# which are legitimate object field keys). Used as the fallback for any
# entity_type that is a custom-object key rather than a Core entity.
_RECORD_RESERVED: set[str] = {
    "id",
    "organization_id",
    "object_definition_id",
    "data",
    "created_at",
    "updated_at",
    "deleted_at",
    "is_deleted",
    "created_by",
    "updated_by",
}


# A custom-object key must not collide with a Core custom-field entity type
# (lead/contact) or a routing/system word. Legitimate business names a tenant
# may model as objects (customer, company, property, policy, loan…) ARE allowed.
RESERVED_OBJECT_KEYS: set[str] = SUPPORTED_ENTITY_TYPES | {
    "record", "records", "object", "objects", "id", "metadata",
}


def is_supported_entity_type(entity_type: str) -> bool:
    return entity_type in SUPPORTED_ENTITY_TYPES


def is_reserved_object_key(key: str) -> bool:
    return key.lower() in RESERVED_OBJECT_KEYS


def is_reserved_key(entity_type: str, key: str) -> bool:
    """True if `key` collides with a system-controlled field for the entity.

    Core entities (lead/contact) reserve their first-class columns; any other
    entity_type is a custom object, whose records only reserve record system
    columns (so business keys like ``name`` are allowed)."""
    reserved = RESERVED_KEYS.get(entity_type, _RECORD_RESERVED)
    return key.lower() in reserved

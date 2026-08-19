"""Central registry of custom-field types for the CRM-Core Custom Fields Engine.

This is the single source of truth for which `field_type` values are valid and
how they are categorised (numeric, option-backed, boolean). The validation
engine, schemas and services all dispatch through here so a new field type is
added in exactly one place.

Belongs to CRM Core — imports no industry (dental/real-estate/…) modules.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class CustomFieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    SELECT = "select"
    MULTISELECT = "multiselect"
    ENTITY_REFERENCE = "entity_reference"  # Phase 4.2: reference to custom-object record(s)


# The 13 canonical types.
CANONICAL_FIELD_TYPES: set[str] = {t.value for t in CustomFieldType}

# "checkbox" was the original boolean type before Phase 4.1. It stays valid and
# is treated everywhere as a boolean so existing definitions/stored values and
# the existing frontend keep working. Do NOT migrate stored "checkbox" defs.
LEGACY_FIELD_TYPE_ALIASES: dict[str, str] = {"checkbox": CustomFieldType.BOOLEAN.value}

# Everything the API/service will accept on input.
ALL_ACCEPTED_FIELD_TYPES: set[str] = CANONICAL_FIELD_TYPES | set(LEGACY_FIELD_TYPE_ALIASES)

# Categories used by the validation engine.
NUMERIC_TYPES: set[str] = {
    CustomFieldType.NUMBER.value,
    CustomFieldType.CURRENCY.value,
    CustomFieldType.PERCENTAGE.value,
}
OPTION_TYPES: set[str] = {
    CustomFieldType.SELECT.value,
    CustomFieldType.MULTISELECT.value,
}
BOOLEAN_TYPES: set[str] = {CustomFieldType.BOOLEAN.value, "checkbox"}
TEXTUAL_TYPES: set[str] = {
    CustomFieldType.TEXT.value,
    CustomFieldType.TEXTAREA.value,
    CustomFieldType.EMAIL.value,
    CustomFieldType.PHONE.value,
    CustomFieldType.URL.value,
}
# Types whose stored value is (or may be) a list.
LIST_TYPES: set[str] = {CustomFieldType.MULTISELECT.value}
REFERENCE_TYPES: set[str] = {CustomFieldType.ENTITY_REFERENCE.value}


def canonical_type(field_type: str) -> str:
    """Resolve legacy aliases (e.g. checkbox → boolean) to the canonical value."""
    return LEGACY_FIELD_TYPE_ALIASES.get(field_type, field_type)


def is_valid_field_type(field_type: str) -> bool:
    return field_type in ALL_ACCEPTED_FIELD_TYPES


# ── Select / multiselect option normalisation (G5) ─────────────────────────────
# Canonical option shape is [{"value": str, "label": str}]. Legacy definitions
# stored plain strings (["a", "b"]); we accept both and coerce to the canonical
# shape on write so downstream code only ever deals with one representation,
# while stored JSON stays backward compatible.

def normalize_options(options: Any) -> list[dict[str, str]] | None:
    """Coerce any accepted option representation to [{value,label}]."""
    if options is None:
        return None
    if not isinstance(options, (list, tuple)):
        raise ValueError("options must be a list")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for opt in options:
        if isinstance(opt, str):
            value = opt.strip()
            label = value
        elif isinstance(opt, dict):
            raw_value = opt.get("value", opt.get("label"))
            if raw_value is None:
                raise ValueError("option object must have a 'value'")
            value = str(raw_value).strip()
            label = str(opt.get("label", value)).strip() or value
        else:
            raise ValueError("option must be a string or {value,label} object")
        if value == "":
            raise ValueError("option value cannot be empty")
        if value in seen:
            raise ValueError(f"duplicate option value: {value}")
        seen.add(value)
        normalized.append({"value": value, "label": label})
    return normalized


def option_values(options: Any) -> set[str]:
    """Return the set of valid stored values from any option representation."""
    normalized = normalize_options(options) or []
    return {o["value"] for o in normalized}

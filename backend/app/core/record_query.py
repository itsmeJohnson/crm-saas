"""Typed, tenant-safe filter/sort engine for custom-object records.

ALL dynamic JSON querying goes through here — repositories never hand-roll JSON
expressions. Each filter is validated against the field's *declared type* (so
``value`` on a currency field is compared numerically, a date lexicographically,
etc.) and against a per-type operator allowlist. Invalid field/operator/type
combinations raise ``RecordQueryError`` (HTTP 400) rather than silently
producing wrong results.

Works behind ONE abstraction on both SQLite (tests) and PostgreSQL (prod):
values are extracted with SQLAlchemy JSON indexing (``col.as_string()`` →
``json_extract`` on SQLite, ``->>`` on PG) and cast per type.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import cast, Float, String, or_, not_

from app.core.custom_field_types import canonical_type

# The full, fixed operator set (Phase 4.2).
ALL_OPERATORS: set[str] = {
    "eq", "ne", "gt", "gte", "lt", "lte", "contains", "startswith", "in", "is_empty",
}

_NUMERIC = {"number", "currency", "percentage"}
_DATE = {"date", "datetime"}
_TEXT = {"text", "textarea", "email", "phone", "url"}

# Operators allowed per canonical field type.
_OPS_BY_TYPE: dict[str, set[str]] = {
    **{t: {"eq", "ne", "gt", "gte", "lt", "lte", "in", "is_empty"} for t in _NUMERIC},
    **{t: {"eq", "ne", "gt", "gte", "lt", "lte", "is_empty"} for t in _DATE},
    **{t: {"eq", "ne", "contains", "startswith", "in", "is_empty"} for t in _TEXT},
    "boolean": {"eq", "ne", "is_empty"},
    "select": {"eq", "ne", "in", "is_empty"},
    "multiselect": {"contains", "is_empty"},
    "entity_reference": {"eq", "ne", "contains", "is_empty"},
}

_TRUTHY = ["true", "1", "True"]
_FALSY = ["false", "0", "False"]


class RecordQueryError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_filter"):
        super().__init__(message)
        self.message = message
        self.code = code


def allowed_operators(field_type: str) -> set[str]:
    return _OPS_BY_TYPE.get(canonical_type(field_type), set())


def _is_multi_reference(definition) -> bool:
    return bool((definition.validation_rules or {}).get("multiple"))


def _coerce_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def build_filter_expressions(model, defs_by_key: dict, filters: list[dict]) -> list:
    """Translate a list of {field, op, value} into SQLAlchemy expressions.

    `defs_by_key` MUST contain only active + filterable definitions — that is the
    guardrail preventing arbitrary JSON-path querying.
    """
    if filters is None:
        return []
    if not isinstance(filters, list):
        raise RecordQueryError("filters must be a list")

    exprs = []
    for f in filters:
        if not isinstance(f, dict):
            raise RecordQueryError("each filter must be an object with field/op/value")
        field = f.get("field")
        op = f.get("op")
        value = f.get("value")

        if field not in defs_by_key:
            raise RecordQueryError(f"Unknown or non-filterable field '{field}'", code="unknown_field")
        if op not in ALL_OPERATORS:
            raise RecordQueryError(f"Unknown operator '{op}'", code="unknown_operator")

        definition = defs_by_key[field]
        ftype = canonical_type(definition.field_type)
        if op not in allowed_operators(ftype):
            raise RecordQueryError(
                f"Operator '{op}' is not valid for field type '{ftype}'", code="operator_type_mismatch"
            )

        exprs.append(_build_one(model, field, ftype, op, value, definition))
    return exprs


def _build_one(model, field: str, ftype: str, op: str, value: Any, definition):
    col = model.data[field]
    # Force a SQL-level text cast so comparisons use text affinity on BOTH engines
    # (SQLite json_extract yields native ints/reals for numeric/boolean JSON, which
    # otherwise mis-compare against string literals).
    text_col = cast(col.as_string(), String)

    if op == "is_empty":
        empty = or_(col.is_(None), text_col == "")
        return empty if _coerce_bool(value if value is not None else True) else not_(empty)

    if ftype in _NUMERIC:
        num = cast(text_col, Float)
        if op == "in":
            return num.in_([_to_float(v, field) for v in _as_list(value, field)])
        v = _to_float(value, field)
        return {
            "eq": num == v, "ne": num != v,
            "gt": num > v, "gte": num >= v, "lt": num < v, "lte": num <= v,
        }[op]

    if ftype in _DATE:
        # ISO-8601 strings sort lexicographically → correct for range operators.
        v = str(value)
        return {
            "eq": text_col == v, "ne": text_col != v,
            "gt": text_col > v, "gte": text_col >= v, "lt": text_col < v, "lte": text_col <= v,
        }[op]

    if ftype == "boolean":
        want = _coerce_bool(value)
        in_truthy = text_col.in_(_TRUTHY)
        if op == "eq":
            return in_truthy if want else not_(in_truthy)
        # ne
        return not_(in_truthy) if want else in_truthy

    if ftype == "multiselect" or (ftype == "entity_reference" and _is_multi_reference(definition)):
        # Stored as a JSON array; membership check via serialized text (cross-DB).
        return text_col.like(f'%"{value}"%')

    # Scalar string types: text/select/single entity_reference.
    if op == "in":
        return text_col.in_([str(v) for v in _as_list(value, field)])
    return {
        "eq": text_col == str(value),
        "ne": text_col != str(value),
        "contains": text_col.ilike(f"%{value}%"),
        "startswith": text_col.ilike(f"{value}%"),
    }[op]


def build_order_by(model, defs_by_key: dict, sort: str | None):
    """Parse a `field:asc|desc` sort spec into an ORDER BY, validated + typed."""
    if not sort:
        return None
    field, _, direction = sort.partition(":")
    field = field.strip()
    direction = (direction or "asc").strip().lower()
    if field not in defs_by_key:
        raise RecordQueryError(f"Cannot sort by unknown or non-filterable field '{field}'", code="unknown_field")
    if direction not in ("asc", "desc"):
        raise RecordQueryError(f"Invalid sort direction '{direction}'")

    definition = defs_by_key[field]
    ftype = canonical_type(definition.field_type)
    col = model.data[field].as_string()
    order_col = cast(col, Float) if ftype in _NUMERIC else col
    return order_col.desc() if direction == "desc" else order_col.asc()


def _as_list(value: Any, field: str) -> list:
    if isinstance(value, (list, tuple)):
        return list(value)
    raise RecordQueryError(f"Operator 'in' on '{field}' requires a list value", code="invalid_value")


def _to_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        raise RecordQueryError(f"Field '{field}' expects a numeric value", code="invalid_value")

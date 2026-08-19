import re
import uuid
from datetime import datetime, date
from typing import Any, Dict, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.custom_field_definition import CustomFieldDefinition
from app.core.custom_field_types import (
    canonical_type,
    option_values,
    NUMERIC_TYPES,
    BOOLEAN_TYPES,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
_PHONE_RE = re.compile(r"^\+?\d{6,15}$")


class MetadataValidationError(ValueError):
    """Exception raised when metadata validation fails.

    Carries an optional structured payload (field/code) while ``str(e)`` still
    returns the human message so existing callers that do ``detail=str(e)``
    keep working unchanged.
    """
    def __init__(self, message: str, *, field: str | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.code = code

    def to_dict(self) -> dict:
        return {"field": self.field, "code": self.code, "message": self.message}


class MetadataValidationEngine:
    @staticmethod
    async def validate_and_sanitize(
        db: AsyncSession,
        model_class: Any,
        org_id: uuid.UUID,
        definitions: List[CustomFieldDefinition],
        payload: Dict[str, Any],
        exclude_id: uuid.UUID | None = None,
        json_field: str = "custom_fields",
        extra_unique_filters: list | None = None,
    ) -> Dict[str, Any]:
        """
        Validates custom field values against custom field definitions.
        Ensures type constraints, validation rules (required, min/max, regex, uniqueness),
        and applies default values.
        Returns a sanitized dictionary containing only valid custom field values.
        """
        # Build map of active definitions
        def_map = {d.key: d for d in definitions if d.is_active}

        # 1. Reject unknown keys
        for key in payload.keys():
            if key not in def_map:
                raise MetadataValidationError(
                    f"Unknown custom field key: '{key}'", field=key, code="unknown_field"
                )

        sanitized: Dict[str, Any] = {}

        # 2. Iterate definitions to check required, type-safety, min/max, regex, unique, defaults
        for key, definition in def_map.items():
            raw = payload.get(key)
            val = raw
            rules = definition.validation_rules or {}
            ftype = canonical_type(definition.field_type)

            # --- Normalization Step (textual values) ---
            if isinstance(val, str):
                val = val.strip()
                if ftype == "email" or rules.get("format") == "email" or "email" in key.lower():
                    val = val.lower()
                elif ftype == "phone" or rules.get("format") == "phone" or "phone" in key.lower():
                    val = re.sub(r"[^\d+]", "", val)

            # Default value check
            if val is None:
                if definition.default_value is not None:
                    val = definition.default_value
                else:
                    if rules.get("required") is True:
                        raise MetadataValidationError(
                            f"Custom field '{definition.label}' is required",
                            field=key, code="required",
                        )
                    continue

            # Skip validation only when the RAW input was genuinely blank. (A
            # non-empty input that normalisation reduced to "" — e.g. a phone of
            # "abc" — must still fail type validation, not be silently dropped.)
            raw_blank = isinstance(raw, str) and raw.strip() == ""
            if raw_blank and ftype not in BOOLEAN_TYPES:
                if rules.get("required") is True:
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' is required",
                        field=key, code="required",
                    )
                continue

            # Read only validation — reject attempts to set a read-only field.
            if definition.read_only:
                raise MetadataValidationError(
                    f"Custom field '{definition.label}' is read-only",
                    field=key, code="read_only",
                )

            val = MetadataValidationEngine._validate_value(key, definition, ftype, rules, val)

            # entity_reference: verify each referenced record exists in THIS tenant
            # (blocks cross-tenant references and dangling ids).
            if ftype == "entity_reference":
                await MetadataValidationEngine._validate_reference_exists(db, org_id, key, definition, val)

            # Unique validation check against DB (scalar-comparable types only)
            if rules.get("unique") is True:
                json_col = getattr(model_class, json_field)
                query = select(func.count(model_class.id)).filter(
                    model_class.organization_id == org_id,
                    model_class.is_deleted == False,
                    json_col[key].as_string() == str(val)
                )
                for extra in (extra_unique_filters or []):
                    query = query.filter(extra)
                if exclude_id is not None:
                    query = query.filter(model_class.id != exclude_id)
                result = await db.execute(query)
                count = result.scalar() or 0
                if count > 0:
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' value '{val}' is already in use and must be unique",
                        field=key, code="unique",
                    )

            sanitized[key] = val

        return sanitized

    # ── Per-type validation dispatch ───────────────────────────────────────────
    @staticmethod
    def _validate_value(key: str, definition, ftype: str, rules: dict, val: Any) -> Any:
        label = definition.label

        def err(msg: str, code: str):
            return MetadataValidationError(f"Custom field '{label}' {msg}", field=key, code=code)

        # Text-like types
        if ftype in ("text", "textarea"):
            if not isinstance(val, str):
                raise err("must be a string", "invalid_type")
            MetadataValidationEngine._check_length(key, label, rules, val)
            MetadataValidationEngine._check_pattern(key, label, rules, val)
            return val

        if ftype == "email":
            if not isinstance(val, str) or not _EMAIL_RE.match(val):
                raise err("must be a valid email address", "invalid_email")
            MetadataValidationEngine._check_length(key, label, rules, val)
            return val

        if ftype == "url":
            if not isinstance(val, str) or not _URL_RE.match(val):
                raise err("must be a valid URL (http/https)", "invalid_url")
            return val

        if ftype == "phone":
            if not isinstance(val, str) or not _PHONE_RE.match(val):
                raise err("must be a valid phone number", "invalid_phone")
            return val

        # Numeric types
        if ftype in NUMERIC_TYPES:
            try:
                num_val = float(val) if "." in str(val) else int(val)
            except (ValueError, TypeError):
                raise err("must be numeric", "invalid_number")
            min_val = rules.get("min_value")
            max_val = rules.get("max_value")
            # Percentage defaults to a 0–100 range unless explicitly overridden.
            if ftype == "percentage":
                if min_val is None:
                    min_val = 0
                if max_val is None:
                    max_val = 100
            if min_val is not None and num_val < float(min_val):
                raise err(f"value must be at least {min_val}", "min_value")
            if max_val is not None and num_val > float(max_val):
                raise err(f"value must be at most {max_val}", "max_value")
            return num_val

        # Boolean (+ legacy checkbox)
        if ftype in BOOLEAN_TYPES:
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            if s in ("true", "1", "yes"):
                return True
            if s in ("false", "0", "no", ""):
                return False
            raise err("must be a boolean", "invalid_boolean")

        if ftype == "date":
            if isinstance(val, datetime):
                return val.date().isoformat()
            if isinstance(val, date):
                return val.isoformat()
            if isinstance(val, str):
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                    return val
                except ValueError:
                    raise err("must be a valid date in YYYY-MM-DD format", "invalid_date")
            raise err("must be a valid date in YYYY-MM-DD format", "invalid_date")

        if ftype == "datetime":
            if isinstance(val, datetime):
                return val.isoformat()
            if isinstance(val, str):
                try:
                    # Accept ISO-8601, tolerating a trailing Z.
                    datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return val
                except ValueError:
                    raise err("must be a valid ISO-8601 datetime", "invalid_datetime")
            raise err("must be a valid ISO-8601 datetime", "invalid_datetime")

        if ftype == "select":
            valid = option_values(definition.options)
            if val not in valid:
                raise err(
                    f"value must be one of: {', '.join(sorted(map(str, valid)))}",
                    "invalid_option",
                )
            return val

        if ftype == "entity_reference":
            multiple = bool(rules.get("multiple"))
            if multiple:
                if isinstance(val, str):
                    val = [val] if val else []
                if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
                    raise err("must be a list of record references", "invalid_reference")
                return val
            if not isinstance(val, str):
                raise err("must be a single record reference id", "invalid_reference")
            return val

        if ftype == "multiselect":
            if isinstance(val, str):
                # Tolerate a single value or comma-separated string.
                val = [v.strip() for v in val.split(",") if v.strip()] if val else []
            if not isinstance(val, list):
                raise err("must be a list of values", "invalid_type")
            valid = option_values(definition.options)
            invalid = [v for v in val if v not in valid]
            if invalid:
                raise err(
                    f"contains invalid option(s): {', '.join(map(str, invalid))}",
                    "invalid_option",
                )
            return val

        # Unknown/unsupported type falls back to passthrough (should not happen —
        # definition creation validates the type up front).
        return val

    @staticmethod
    def _check_length(key: str, label: str, rules: dict, val: str) -> None:
        min_len = rules.get("min_length")
        max_len = rules.get("max_length")
        if min_len is not None and len(val) < int(min_len):
            raise MetadataValidationError(
                f"Custom field '{label}' must be at least {min_len} characters long",
                field=key, code="min_length",
            )
        if max_len is not None and len(val) > int(max_len):
            raise MetadataValidationError(
                f"Custom field '{label}' must not exceed {max_len} characters",
                field=key, code="max_length",
            )

    @staticmethod
    async def _validate_reference_exists(db, org_id, key: str, definition, val) -> None:
        """Ensure entity_reference value(s) point to live records of the configured
        target object WITHIN the same tenant. Lazy-imports the custom-object models
        to avoid an import cycle (both live in CRM Core)."""
        import uuid as _uuid
        from app.models.custom_object import CustomObjectDefinition, CustomObjectRecord

        rules = definition.validation_rules or {}
        target_key = rules.get("reference_object")
        if not target_key:
            raise MetadataValidationError(
                f"Custom field '{definition.label}' is a reference but has no target object configured",
                field=key, code="reference_misconfigured",
            )
        ids = val if isinstance(val, list) else [val]
        ids = [i for i in ids if i]
        if not ids:
            return
        try:
            uid_list = [_uuid.UUID(str(i)) for i in ids]
        except (ValueError, TypeError):
            raise MetadataValidationError(
                f"Custom field '{definition.label}' has an invalid reference id",
                field=key, code="invalid_reference",
            )

        target = (await db.execute(
            select(CustomObjectDefinition).filter(
                CustomObjectDefinition.organization_id == org_id,
                CustomObjectDefinition.key == target_key,
                CustomObjectDefinition.is_active == True,
                CustomObjectDefinition.is_deleted == False,
            )
        )).scalars().first()
        if not target:
            raise MetadataValidationError(
                f"Custom field '{definition.label}' references an unknown object '{target_key}'",
                field=key, code="invalid_reference",
            )

        count = (await db.execute(
            select(func.count(CustomObjectRecord.id)).filter(
                CustomObjectRecord.organization_id == org_id,
                CustomObjectRecord.object_definition_id == target.id,
                CustomObjectRecord.is_deleted == False,
                CustomObjectRecord.id.in_(uid_list),
            )
        )).scalar() or 0
        if count != len(set(uid_list)):
            raise MetadataValidationError(
                f"Custom field '{definition.label}' references records that do not exist in your organization",
                field=key, code="invalid_reference",
            )

    @staticmethod
    def _check_pattern(key: str, label: str, rules: dict, val: str) -> None:
        pattern = rules.get("pattern")
        if pattern:
            try:
                if not re.match(pattern, val):
                    raise MetadataValidationError(
                        f"Custom field '{label}' does not match required format",
                        field=key, code="pattern",
                    )
            except re.error:
                pass

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.custom_field_definition import CustomFieldDefinition


class MetadataValidationError(ValueError):
    """Exception raised when metadata validation fails."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MetadataValidationEngine:
    @staticmethod
    async def validate_and_sanitize(
        db: AsyncSession,
        model_class: Any,
        org_id: uuid.UUID,
        definitions: List[CustomFieldDefinition],
        payload: Dict[str, Any],
        exclude_id: uuid.UUID | None = None
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
                raise MetadataValidationError(f"Unknown custom field key: '{key}'")

        sanitized = {}

        # 2. Iterate definitions to check required, type-safety, min/max, regex, unique, defaults
        for key, definition in def_map.items():
            val = payload.get(key)
            rules = definition.validation_rules or {}

            # --- Normalization Step ---
            if isinstance(val, str):
                # Trimmed text
                val = val.strip()
                # Email formatting (lower case)
                if rules.get("format") == "email" or key == "email" or "email" in key.lower():
                    val = val.lower()
                # Phone formatting (keep only digits and + symbol)
                elif rules.get("format") == "phone" or key == "phone" or "phone" in key.lower():
                    val = re.sub(r"[^\d+]", "", val)
            
            # Default value check
            if val is None:
                if definition.default_value is not None:
                    val = definition.default_value
                else:
                    # Check if required
                    if rules.get("required") is True:
                        raise MetadataValidationError(f"Custom field '{definition.label}' is required")
                    continue

            # Skip validation if value is empty and not required
            if val == "":
                if rules.get("required") is True:
                    raise MetadataValidationError(f"Custom field '{definition.label}' is required")
                continue

            # Read only validation
            if definition.read_only:
                # If we're updating and value changed, block it
                # For simplicity, we block modifying read-only fields if provided in the payload
                raise MetadataValidationError(f"Custom field '{definition.label}' is read-only")

            # Field type validations
            if definition.field_type == "text":
                if not isinstance(val, str):
                    raise MetadataValidationError(f"Custom field '{definition.label}' must be a string")
                
                # Length checks
                min_len = rules.get("min_length")
                max_len = rules.get("max_length")
                if min_len is not None and len(val) < int(min_len):
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' must be at least {min_len} characters long"
                    )
                if max_len is not None and len(val) > int(max_len):
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' must not exceed {max_len} characters"
                    )
                
                # Regex patterns check
                pattern = rules.get("pattern")
                if pattern:
                    try:
                        if not re.match(pattern, val):
                            raise MetadataValidationError(
                                f"Custom field '{definition.label}' does not match required format"
                            )
                    except re.error:
                        # Fallback if pattern is invalid regex
                        pass

            elif definition.field_type == "number":
                # Convert to numeric
                try:
                    num_val = float(val) if "." in str(val) else int(val)
                except (ValueError, TypeError):
                    raise MetadataValidationError(f"Custom field '{definition.label}' must be numeric")

                # Min/max checks
                min_val = rules.get("min_value")
                max_val = rules.get("max_value")
                if min_val is not None and num_val < float(min_val):
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' value must be at least {min_val}"
                    )
                if max_val is not None and num_val > float(max_val):
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' value must be at most {max_val}"
                    )
                val = num_val

            elif definition.field_type == "date":
                # ISO date format check
                try:
                    if isinstance(val, str):
                        # Validate format YYYY-MM-DD
                        datetime.strptime(val, "%Y-%m-%d")
                    elif isinstance(val, (datetime, datetime.date)):
                        val = val.strftime("%Y-%m-%d")
                    else:
                        raise ValueError()
                except ValueError:
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' must be a valid date in YYYY-MM-DD format"
                    )

            elif definition.field_type == "select":
                # Choices check
                options = definition.options or []
                if val not in options:
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' value must be one of: {', '.join(map(str, options))}"
                    )

            elif definition.field_type == "checkbox":
                if not isinstance(val, bool):
                    if str(val).lower() in ("true", "1", "yes"):
                        val = True
                    elif str(val).lower() in ("false", "0", "no"):
                        val = False
                    else:
                        raise MetadataValidationError(f"Custom field '{definition.label}' must be a boolean")

            # Unique validation check against DB
            if rules.get("unique") is True:
                # Query model_class.custom_fields for duplicate
                query = select(func.count(model_class.id)).filter(
                    model_class.organization_id == org_id,
                    model_class.is_deleted == False,
                    model_class.custom_fields[key].as_string() == str(val)
                )
                if exclude_id is not None:
                    query = query.filter(model_class.id != exclude_id)
                
                result = await db.execute(query)
                count = result.scalar() or 0
                if count > 0:
                    raise MetadataValidationError(
                        f"Custom field '{definition.label}' value '{val}' is already in use and must be unique"
                    )

            sanitized[key] = val

        return sanitized

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

_FIELD_TYPE_DOC = (
    "One of: text, textarea, number, currency, percentage, date, datetime, "
    "boolean, email, phone, url, select, multiselect (legacy: checkbox)"
)

# Options accept either legacy plain strings (["a","b"]) or the canonical
# {value,label} shape; the service normalises them to {value,label} on write.
OptionInput = str | dict[str, Any]


class CustomFieldDefinitionCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, pattern="^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=100)
    field_type: str = Field("text", description=_FIELD_TYPE_DOC)
    options: list[OptionInput] | None = None
    placeholder: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=500)
    default_value: Any | None = None
    validation_rules: dict[str, Any] | None = None
    section: str | None = Field(None, max_length=100)
    is_active: bool = True
    read_only: bool = False
    visible: bool = True
    searchable: bool = True
    filterable: bool = True
    exportable: bool = True
    importable: bool = True

class CustomFieldDefinitionUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=100)
    options: list[OptionInput] | None = None
    placeholder: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=500)
    default_value: Any | None = None
    validation_rules: dict[str, Any] | None = None
    section: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    read_only: bool | None = None
    visible: bool | None = None
    searchable: bool | None = None
    filterable: bool | None = None
    exportable: bool | None = None
    importable: bool | None = None

class CustomFieldDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: str
    key: str
    label: str
    field_type: str
    # Normalised to [{value,label}] on write; legacy rows may still be [str].
    options: list[OptionInput] | None
    placeholder: str | None
    description: str | None
    default_value: Any | None
    validation_rules: dict[str, Any] | None
    section: str | None
    is_active: bool
    read_only: bool
    visible: bool
    searchable: bool
    filterable: bool
    exportable: bool
    importable: bool
    created_at: datetime
    updated_at: datetime

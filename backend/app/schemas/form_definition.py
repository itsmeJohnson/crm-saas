import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class FormFieldEntry(BaseModel):
    """A field placement inside a form section, with per-form presentation overrides."""
    key: str = Field(..., min_length=1, max_length=80)
    required: bool | None = None    # override: force required in THIS form
    hidden: bool | None = None      # override: hide in THIS form
    read_only: bool | None = None   # override: read-only in THIS form


class FormSection(BaseModel):
    title: str | None = Field(None, max_length=150)
    columns: int | None = Field(None, ge=1, le=4)
    fields: list[FormFieldEntry] = Field(default_factory=list)


class FormSchema(BaseModel):
    sections: list[FormSection] = Field(default_factory=list)


class FormDefinitionCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=80, pattern="^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=500)
    form_schema: FormSchema = Field(default_factory=FormSchema, alias="schema")
    is_active: bool = True
    is_default: bool = False

    model_config = ConfigDict(populate_by_name=True)


class FormDefinitionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=500)
    form_schema: FormSchema | None = Field(None, alias="schema")
    is_active: bool | None = None
    is_default: bool | None = None

    model_config = ConfigDict(populate_by_name=True)


class FormDefinitionResponse(BaseModel):
    # populate_by_name lets the ORM attribute `schema` fill `form_schema`;
    # serialization_alias keeps the JSON key `schema` for the frontend.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: str
    key: str
    name: str
    description: str | None = None
    form_schema: dict[str, Any] | None = Field(
        None, validation_alias="schema", serialization_alias="schema"
    )
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

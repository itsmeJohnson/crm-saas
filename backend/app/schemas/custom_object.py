import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CustomObjectDefinitionCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, pattern="^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=150)
    label_plural: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=20)
    display_field_key: str | None = Field(None, max_length=80)


class CustomObjectDefinitionUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=150)
    label_plural: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=20)
    display_field_key: str | None = Field(None, max_length=80)
    is_active: bool | None = None


class CustomObjectDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    key: str
    label: str
    label_plural: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    display_field_key: str | None = None
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime


class CustomObjectRecordCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class CustomObjectRecordUpdate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class CustomObjectRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    object_definition_id: uuid.UUID
    data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CustomObjectRecordListResponse(BaseModel):
    items: list[CustomObjectRecordResponse]
    total: int
    page: int
    page_size: int

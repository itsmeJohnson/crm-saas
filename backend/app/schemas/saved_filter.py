import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SavedFilterCreate(BaseModel):
    name: str = Field(..., max_length=150)
    entity_type: str = Field("lead", max_length=50)
    definition: dict[str, Any]
    is_shared: bool = False


class SavedFilterUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    definition: dict[str, Any] | None = None
    is_shared: bool | None = None


class SavedFilterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    entity_type: str
    definition: dict[str, Any]
    is_shared: bool
    created_at: datetime
    updated_at: datetime

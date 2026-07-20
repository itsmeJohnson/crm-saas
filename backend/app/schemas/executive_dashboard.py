import uuid
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class WidgetMeta(BaseModel):
    id: str
    label: str
    category: str
    drill: str | None = None


class CatalogResponse(BaseModel):
    personas: list[str]
    scopes: list[str]
    widgets: list[WidgetMeta]
    persona_layouts: dict[str, list[str]]


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    persona: str
    scope: str
    from_: str = Field(alias="from")
    to: str
    generated_at: str
    widgets: list[str]
    blocks: dict[str, Any]


class DashboardRequest(BaseModel):
    persona: str | None = None
    scope: str | None = None
    widgets: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None


class ViewCreate(BaseModel):
    name: str = Field(..., max_length=120)
    persona: str | None = None
    scope: str | None = None
    widgets: list[str] | None = None
    is_default: bool = False


class ViewUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    persona: str | None = None
    scope: str | None = None
    widgets: list[str] | None = None
    is_default: bool | None = None


class ViewResponse(BaseModel):
    id: str
    name: str
    persona: str
    scope: str
    widgets: list[str]
    is_default: bool
    created_at: str | None = None

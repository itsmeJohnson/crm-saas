from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    viz_type: str
    dataset: str
    config: dict = {}
    filters: dict | list | None = None


class DrilldownRequest(BaseModel):
    dataset: str
    field: str
    value: str | int | float | None = None
    filters: dict | list | None = None
    limit: int = Field(50, ge=1, le=500)


class VizCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = Field(None, max_length=300)
    viz_type: str
    dataset: str
    config: dict = {}
    filters: dict | list | None = None
    visibility: str = "organization"
    is_pinned: bool = False


class VizUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=300)
    viz_type: str | None = None
    dataset: str | None = None
    config: dict | None = None
    filters: dict | list | None = None
    visibility: str | None = None
    is_pinned: bool | None = None

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# --- Stage Schemas ---

class PipelineStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    order_position: int | None = Field(None, description="Position in the pipeline flow. Must be a positive integer.")
    is_system_default: bool = Field(False)
    color: str = Field("#4F46E5")
    probability: int = Field(0, ge=0, le=100)
    is_won: bool = Field(False)
    is_lost: bool = Field(False)
    is_active: bool = Field(True)

class PipelineStageCreate(PipelineStageBase):
    pipeline_id: uuid.UUID | None = Field(None, description="Pipeline this stage belongs to. If omitted, maps to default pipeline.")

class PipelineStageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    order_position: int | None = Field(None, ge=1)
    is_system_default: bool | None = None
    color: str | None = None
    probability: int | None = Field(None, ge=0, le=100)
    is_won: bool | None = None
    is_lost: bool | None = None
    is_active: bool | None = None

class PipelineStageOrderUpdate(BaseModel):
    stage_id: uuid.UUID
    new_position: int = Field(..., ge=1)

class PipelineStageReorderRequest(BaseModel):
    orders: list[PipelineStageOrderUpdate]

class PipelineStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    pipeline_id: uuid.UUID
    name: str
    order_position: int
    is_system_default: bool
    color: str
    probability: int
    is_won: bool
    is_lost: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

# --- Pipeline Schemas ---

class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_default: bool = Field(False)
    is_active: bool = Field(True)

class PipelineUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None

class PipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stages: list[PipelineStageResponse] = []

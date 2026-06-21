import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PipelineStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    order_position: int | None = Field(None, description="Position in the pipeline flow. Must be a positive integer.")
    is_system_default: bool = Field(False)

class PipelineStageCreate(PipelineStageBase):
    pass

class PipelineStageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    order_position: int | None = Field(None, ge=1)
    is_system_default: bool | None = None

class PipelineStageOrderUpdate(BaseModel):
    stage_id: uuid.UUID
    new_position: int = Field(..., ge=1)

class PipelineStageReorderRequest(BaseModel):
    orders: list[PipelineStageOrderUpdate]

class PipelineStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    order_position: int
    is_system_default: bool
    created_at: datetime
    updated_at: datetime

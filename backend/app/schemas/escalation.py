import uuid
from pydantic import BaseModel, ConfigDict, Field


class EscalationConfigUpdate(BaseModel):
    is_active: bool | None = None
    idle_days: int | None = Field(None, ge=1, le=365)


class EscalationConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    idle_days: int

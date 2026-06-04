import uuid
from pydantic import BaseModel, ConfigDict

class AssignmentConfigUpdate(BaseModel):
    is_active: bool

class AssignmentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: uuid.UUID
    is_active: bool
    last_assigned_user_id: uuid.UUID | None = None

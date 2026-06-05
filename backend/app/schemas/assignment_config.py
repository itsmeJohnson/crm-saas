import uuid
from pydantic import BaseModel, ConfigDict
from app.models.assignment_config import AssignmentStrategy

class AssignmentConfigUpdate(BaseModel):
    is_active: bool | None = None
    assignment_strategy: AssignmentStrategy | None = None

class AssignmentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: uuid.UUID
    is_active: bool
    last_assigned_user_id: uuid.UUID | None = None
    assignment_strategy: AssignmentStrategy

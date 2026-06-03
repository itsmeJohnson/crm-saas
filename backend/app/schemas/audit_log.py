import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class AuditLogBase(BaseModel):
    action: str
    resource_type: str
    resource_id: str | None = None
    action_metadata: dict | None = None

class AuditLogResponse(AuditLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    created_at: datetime

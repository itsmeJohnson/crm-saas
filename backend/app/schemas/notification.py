import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    title: str
    body: str
    link_url: str | None = None
    is_read: bool
    read_at: datetime | None = None
    action_metadata: dict | None = None
    created_at: datetime

class UnreadCountResponse(BaseModel):
    unread_count: int

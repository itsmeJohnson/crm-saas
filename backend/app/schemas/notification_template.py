import uuid
from pydantic import BaseModel
from datetime import datetime


class NotificationTemplateCreate(BaseModel):
    template_key: str
    template_name: str
    channel: str = "email"
    subject: str | None = None
    body: str = ""
    variables: list[str] | None = None
    is_active: bool = True
    category: str = "billing"
    description: str | None = None


class NotificationTemplateUpdate(BaseModel):
    template_name: str | None = None
    subject: str | None = None
    body: str | None = None
    variables: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


class NotificationTemplateResponse(BaseModel):
    id: uuid.UUID
    template_key: str
    template_name: str
    channel: str
    subject: str | None = None
    body: str
    variables: list | None = None
    is_active: bool
    category: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

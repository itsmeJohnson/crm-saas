import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NoteBase(BaseModel):
    content: str
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    content: str

class NoteResponse(NoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

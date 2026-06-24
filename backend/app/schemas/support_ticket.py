import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class SupportTicketCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=255)
    priority: str = Field("Medium", pattern="^(Low|Medium|High|Critical)$")
    description: str = Field(..., min_length=10, max_length=5000)
    attachments: Optional[List[str]] = None

class SupportTicketUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(Open|In_Progress|Resolved|Closed)$")
    priority: Optional[str] = Field(None, pattern="^(Low|Medium|High|Critical)$")
    resolution: Optional[str] = None

class SupportTicketCommentResponse(BaseModel):
    author: str
    content: str
    timestamp: str

class SupportTicketHistoryResponse(BaseModel):
    status: str
    by: str
    timestamp: str

class SupportTicketResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    subject: str
    ticket_number: str
    priority: str
    description: str
    attachments: Optional[List[str]] = None
    status: str
    assigned_to_id: Optional[uuid.UUID] = None
    resolution: Optional[str] = None
    comments: List[SupportTicketCommentResponse] = []
    history: List[SupportTicketHistoryResponse] = []
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

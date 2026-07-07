import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CallItem(BaseModel):
    id: str
    subject: str
    description: Optional[str] = None
    direction: Optional[str] = None
    disposition: Optional[str] = None
    status: str
    duration: Optional[int] = None
    recording_url: Optional[str] = None
    tags: List[str] = []
    timestamp: datetime
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    lead_id: Optional[str] = None
    lead_title: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None


class CallHistoryResponse(BaseModel):
    items: List[CallItem]
    total: int


class CallTagsUpdate(BaseModel):
    tags: List[str] = Field(..., max_length=20, description="Full replacement list of tags for the call.")


class ReportBucket(BaseModel):
    label: str
    count: int


class CallReportResponse(BaseModel):
    total: int
    missed: int
    avg_duration: int
    connect_rate: float
    connected: int
    dispositioned: int
    by_direction: List[ReportBucket]
    by_disposition: List[ReportBucket]
    by_agent: List[ReportBucket]
    by_day: List[ReportBucket]


class CurrentCall(BaseModel):
    activity_id: str
    direction: Optional[str] = None
    lead_id: Optional[str] = None
    lead_title: Optional[str] = None
    started_at: datetime


class QueueAgent(BaseModel):
    user_id: str
    user_name: str
    state: str
    since: Optional[str] = None
    current_call: Optional[CurrentCall] = None


class CallQueueResponse(BaseModel):
    pending_queue: int
    agents: List[QueueAgent]

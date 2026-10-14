import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SequenceStepIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    delay_hours: int = Field(0, ge=0, le=8760)  # up to a year
    is_active: bool = True


class SequenceStepOut(SequenceStepIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    step_order: int


class EmailSequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    trigger: str = Field("manual", pattern="^(manual|lead_created)$")
    is_active: bool = True
    steps: list[SequenceStepIn] = Field(default_factory=list)


class EmailSequenceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    trigger: str | None = Field(None, pattern="^(manual|lead_created)$")
    is_active: bool | None = None
    steps: list[SequenceStepIn] | None = None


class EmailSequenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    trigger: str
    is_active: bool
    created_at: datetime
    steps: list[SequenceStepOut] = []


class EnrollRequest(BaseModel):
    lead_id: uuid.UUID


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence_id: uuid.UUID
    lead_id: uuid.UUID
    current_step: int
    status: str
    next_run_at: datetime | None = None
    last_sent_at: datetime | None = None

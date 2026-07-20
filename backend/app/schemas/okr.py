import uuid
from pydantic import BaseModel, Field


class KeyResultCreate(BaseModel):
    title: str = Field(..., max_length=200)
    kind: str = "manual"  # manual|metric
    metric: str | None = None
    unit: str | None = None
    start_value: float = 0
    target_value: float
    current_value: float | None = None
    weight: float = Field(1, ge=0.1, le=10)


class KeyResultUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    kind: str | None = None
    metric: str | None = None
    unit: str | None = None
    start_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    weight: float | None = Field(None, ge=0.1, le=10)
    status: str | None = None


class ObjectiveCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=500)
    level: str  # company|department|team|individual
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    cycle_type: str = "quarterly"  # quarterly|annual|custom
    cycle_year: int | None = None
    cycle_quarter: int | None = Field(None, ge=1, le=4)
    start_date: str | None = None  # ISO date, required for custom cycles
    end_date: str | None = None
    status: str = "active"
    key_results: list[KeyResultCreate] = []


class ObjectiveUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)
    owner_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CheckinRequest(BaseModel):
    value: float
    confidence: int | None = Field(None, ge=0, le=100)
    comment: str | None = Field(None, max_length=1000)


class ReviewCreate(BaseModel):
    review_type: str = "review"  # review|feedback
    rating: int | None = Field(None, ge=1, le=5)
    comment: str = Field(..., max_length=1000)

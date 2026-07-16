import uuid
from pydantic import BaseModel, Field


class TrainingCreate(BaseModel):
    user_id: uuid.UUID
    name: str = Field(..., max_length=150)
    category: str | None = Field(None, max_length=60)
    status: str = "completed"
    score: int | None = Field(None, ge=0, le=100)


class TrainingUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    category: str | None = None
    status: str | None = None
    score: int | None = Field(None, ge=0, le=100)


class TrainingResponse(BaseModel):
    id: str
    user_id: str
    name: str
    category: str | None = None
    status: str
    score: int | None = None
    completed_at: str | None = None
    created_at: str | None = None

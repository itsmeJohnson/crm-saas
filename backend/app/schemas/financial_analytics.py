import uuid
from datetime import date
from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    category: str = Field("General", max_length=60)
    amount: float = Field(..., gt=0)
    description: str | None = None
    vendor: str | None = Field(None, max_length=150)
    incurred_at: date | None = None


class ExpenseUpdate(BaseModel):
    category: str | None = Field(None, max_length=60)
    amount: float | None = Field(None, gt=0)
    description: str | None = None
    vendor: str | None = Field(None, max_length=150)
    incurred_at: date | None = None


class ExpenseResponse(BaseModel):
    id: str
    category: str
    amount: float
    description: str | None = None
    vendor: str | None = None
    incurred_at: str | None = None
    created_at: str | None = None

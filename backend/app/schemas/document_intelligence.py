import uuid
from pydantic import BaseModel, Field


class ProcessTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    filename: str = Field("pasted.txt", max_length=255)
    context_type: str | None = None
    context_id: uuid.UUID | None = None


class DocSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    doc_type: str | None = None
    limit: int = Field(10, ge=1, le=50)


class SummarizeDocRequest(BaseModel):
    length: int = Field(5, ge=1, le=10)

import uuid
from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    parent_id: uuid.UUID | None = None
    display_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    parent_id: uuid.UUID | None = None
    display_order: int | None = None


class ArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    summary: str | None = None
    article_type: str = "article"  # article|faq|document
    category_id: uuid.UUID | None = None
    tags: list[str] = []
    visibility: str = "all"  # all|managers|admins
    language: str = "en"
    source_filename: str | None = None


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    content: str | None = None
    summary: str | None = None
    article_type: str | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    visibility: str | None = None
    language: str | None = None
    source_filename: str | None = None
    change_note: str | None = None


class ReviewRequest(BaseModel):
    note: str | None = None


class FeedbackRequest(BaseModel):
    helpful: bool
    comment: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(10, ge=1, le=50)
    article_type: str | None = None


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(8, ge=1, le=20)
    max_chars: int = Field(4000, ge=200, le=16000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

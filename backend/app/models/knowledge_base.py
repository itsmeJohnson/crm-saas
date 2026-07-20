import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class KBCategory(BaseModel):
    """Knowledge category tree (self-referencing hierarchy, org-scoped)."""
    __tablename__ = "kb_categories"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_kb_category_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kb_categories.id"), nullable=True, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class KBArticle(BaseModel):
    """One knowledge item: a long-form article, an FAQ entry (title=question,
    content=answer) or an indexed text document. Carries the approval workflow
    (draft -> pending_review -> published/rejected, or archived), per-role
    visibility and denormalized usage counters."""
    __tablename__ = "kb_articles"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_type: Mapped[str] = mapped_column(String(20), default="article", nullable=False)  # article|faq|document
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)  # draft|pending_review|published|rejected|archived
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kb_categories.id"), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="all", nullable=False)  # all|managers|admins
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)  # for article_type=document

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # embedding index state
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # usage counters (analytics)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KBArticleVersion(BaseModel):
    """Immutable snapshot of an article taken BEFORE each content edit
    (and on restore), so any prior version can be viewed or restored."""
    __tablename__ = "kb_article_versions"
    __table_args__ = (UniqueConstraint("article_id", "version", name="uq_kb_article_version"),)

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class KBChunk(BaseModel):
    """Embedding index entry: one chunk of an article's text plus its vector.
    embedding is a JSON list[float]; embedding_model tags the pipeline that
    produced it (deterministic hash_embed_v1 today, provider models later)."""
    __tablename__ = "kb_chunks"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(40), default="hash_embed_v1", nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KBEvent(BaseModel):
    """Knowledge analytics event stream: views, searches, AI asks and
    helpful/not-helpful feedback."""
    __tablename__ = "kb_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # view|search|ask|feedback
    article_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kb_articles.id"), nullable=True, index=True)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    results_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

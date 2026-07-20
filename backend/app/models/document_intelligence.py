import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, Float, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DIDocument(BaseModel):
    """One processed document: original file metadata, the extracted text,
    deterministic classification + per-type structured extraction, extracted
    tables, optional AI summary and a semantic-search embedding (same
    hash_embed_v1 pipeline as the Knowledge Base)."""
    __tablename__ = "di_documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="upload", nullable=False)  # upload|text|attachment
    context_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # lead|contact|company|customer|activity|task
    context_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default="processed", nullable=False, index=True)  # processed|needs_ocr|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # extracted text (truncated)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    doc_type: Mapped[str] = mapped_column(String(30), default="other", nullable=False, index=True)  # invoice|contract|identity|resume|receipt|report|letter|other
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    classification_signals: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # per-type keyword scores

    extraction: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # common + type-specific fields
    tables: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{headers, rows, source}]
    image_info: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # image understanding metadata
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI summary (via gateway)

    embedding: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(40), default="hash_embed_v1", nullable=False)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

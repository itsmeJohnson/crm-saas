import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Integer, Float, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class RecommendationFeedback(BaseModel):
    """One surfaced recommendation and the user's response to it. Backs both the
    feedback loop (a dismissed rec stops re-surfacing; accepted types get
    up-weighted for that user) and recommendation analytics (acceptance rates).

    rec_key is a stable identity for a specific recommendation (e.g.
    "next_best_action:lead:<uuid>") so re-generation is idempotent per user."""
    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        Index("ix_rec_feedback_user_key", "user_id", "rec_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rec_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    rec_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    action: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)  # pending|accepted|dismissed|snoozed|completed
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

import uuid
from sqlalchemy import String, ForeignKey, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class DashboardView(BaseModel):
    """A user's saved Executive-Dashboard configuration: which persona/scope and
    which widgets (in order) to show. Powers 'Saved Views' + 'Widget
    Configuration'. Personal to the owner; nothing here mutates the underlying
    analytics — it only selects and orders existing widget blocks."""
    __tablename__ = "dashboard_views"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    persona: Mapped[str] = mapped_column(String(20), default="ceo", nullable=False)   # ceo|sales|finance|hr|support|operations|custom
    scope: Mapped[str] = mapped_column(String(20), default="organization", nullable=False)  # organization|branch|department|team
    widgets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # ordered widget ids
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_dashboard_views_org_user", "organization_id", "user_id"),
    )

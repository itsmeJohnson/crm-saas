import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

# Who an announcement is shown to. 'all' = everyone in the org.
ANNOUNCEMENT_AUDIENCES = ("all", "OrgAdmin", "Manager", "Employee")


class Announcement(BaseModel):
    """An org-wide announcement shown on dashboards. Audience-targeted, pinnable,
    and optionally auto-expiring. Distinct from per-user Notifications: this is a
    persistent, broadcast board that managers/admins curate."""
    __tablename__ = "announcements"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), default="all", nullable=False, index=True)  # ANNOUNCEMENT_AUDIENCES
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

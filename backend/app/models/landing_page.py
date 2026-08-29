import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, Integer, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class LandingPage(BaseModel):
    """A tenant-built public landing page with a lead-capture form (Website Engine).

    Content is a single ``config`` JSON (headline, subheadline, body, CTA, hero,
    theme, and the ordered ``form_fields`` to render). The page is served publicly
    at ``/lp/<slug>`` (no auth); a form submission creates a Lead in this org with
    UTM attribution stored on the lead. ``owner_user_id`` is the CRM user captured
    leads are assigned to. Website count per tenant is capped by the plan's
    ``website_limit``.
    """
    __tablename__ = "landing_pages"
    __table_args__ = (UniqueConstraint("slug", name="uq_landing_pages_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)  # public URL segment (globally unique)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {headline, subheadline, body, cta_text, hero_image, theme, form_fields:[...]}
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submissions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

import uuid
from sqlalchemy import String, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class BookingLink(BaseModel):
    """A public, self-service scheduling page for one host. Visitors see the
    host's open slots (derived from org working hours minus existing calendar
    events and holidays) and book one, which creates an Appointment event plus
    an inbound Lead. Modelled after LandingPage: a public slug + an owning host."""

    __tablename__ = "booking_links"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    host_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    advance_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)  # how far ahead visitors may book
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    bookings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

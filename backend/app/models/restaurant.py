"""Restaurant QR-Voucher vertical.

A tenant-scoped loyalty/marketing module:

    Guest scans a table QR  ->  opts in (name + WhatsApp + DOB, explicit consent)
    ->  a single-use Voucher is issued  ->  delivered on WhatsApp
    ->  floor staff scan & "burn" the voucher (authenticated, atomic)
    ->  owner runs WhatsApp campaigns to opted-in guests.

Every table is scoped to `organization_id` (the tenant / restaurant brand). A
brand may run several physical `RestaurantVenue`s (branches); each venue owns a
public `slug` used to resolve the tenant server-side for the public,
unauthenticated scan flow — the restaurant identity is NEVER trusted from client
input (unlike the demo).

Security-relevant design notes live next to the columns they concern.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, DateTime, JSON, Date,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RestaurantVenue(BaseModel):
    """A physical restaurant / branch. Owns the public `slug` that the scan flow
    uses to resolve the tenant, plus branding, the consent copy, and which WABA
    (WhatsApp settings row) its messages are sent from."""
    __tablename__ = "restaurant_venues"
    __table_args__ = (
        # Slug is globally unique so a public /r/{slug} URL maps to exactly one tenant.
        UniqueConstraint("slug", name="uq_restaurant_venue_slug"),
        Index("ix_restaurant_venue_org", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    # WABA/number to send from. NULL => messaging runs in "simulated" mode so the
    # product is fully demoable on-spot before a real number is connected.
    whatsapp_settings_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_settings.id", ondelete="SET NULL"), nullable=True)
    default_offer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurant_offers.id", ondelete="SET NULL",
                   use_alter=True, name="fk_venue_default_offer"),
        nullable=True)

    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    default_country_code: Mapped[str] = mapped_column(String(6), nullable=False, default="91")
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand_color: Mapped[str] = mapped_column(String(9), nullable=False, default="#D97706")
    # Exact consent sentence shown at opt-in; snapshotted onto each guest for DPDP proof.
    consent_text: Mapped[str] = mapped_column(
        Text, nullable=False,
        default=("I agree to receive exclusive dining vouchers, birthday treats and "
                 "offers on WhatsApp. I can reply STOP anytime to opt out."))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    offers: Mapped[list["RestaurantOffer"]] = relationship(
        "RestaurantOffer", back_populates="venue",
        foreign_keys="RestaurantOffer.venue_id")
    tables: Mapped[list["RestaurantTable"]] = relationship(
        "RestaurantTable", back_populates="venue")


class RestaurantOffer(BaseModel):
    """A complimentary item / promotion a QR issues (e.g. "Free Chef's Bruschetta").
    Redemption limits are enforced server-side at issue & burn time."""
    __tablename__ = "restaurant_offers"
    __table_args__ = (
        Index("ix_restaurant_offer_org", "organization_id"),
        Index("ix_restaurant_offer_venue", "venue_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurant_venues.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)  # "Min order ₹800", etc.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Days a freshly issued voucher stays valid before auto-expiring. NULL = no expiry.
    voucher_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=30)
    # How many *active* vouchers one guest may hold for this offer (dedup guard).
    per_guest_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Hard cap on total vouchers ever issued for this offer. NULL = unlimited.
    total_issue_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    venue: Mapped[RestaurantVenue] = relationship(
        "RestaurantVenue", back_populates="offers", foreign_keys=[venue_id])


class RestaurantTable(BaseModel):
    """One physical table's printed QR. The QR encodes /r/{venue_slug}/t/{token};
    `token` is an opaque secret so table URLs can't be trivially enumerated."""
    __tablename__ = "restaurant_tables"
    __table_args__ = (
        UniqueConstraint("token", name="uq_restaurant_table_token"),
        UniqueConstraint("venue_id", "label", name="uq_restaurant_table_venue_label"),
        Index("ix_restaurant_table_org", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurant_venues.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)  # "T-04", "Rooftop 2"
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    # Which offer this table's QR issues; falls back to venue.default_offer_id.
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurant_offers.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    venue: Mapped[RestaurantVenue] = relationship("RestaurantVenue", back_populates="tables")


class RestaurantGuest(BaseModel):
    """An opted-in diner. Deduplicated per tenant by normalized phone. Holds the
    DPDP consent proof (snapshot text + ip + timestamp) and marketing status.

    PII (phone/email/dob) is only ever returned by authenticated staff endpoints,
    masked for non-admin roles. There is no public endpoint that returns this."""
    __tablename__ = "restaurant_guests"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone", name="uq_restaurant_guest_org_phone"),
        Index("ix_restaurant_guest_org_status", "organization_id", "status"),
        Index("ix_restaurant_guest_phone", "phone"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurant_venues.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Stored E.164 without '+', e.g. "919880194821". Normalized server-side.
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    dob: Mapped[datetime | None] = mapped_column(Date, nullable=True)

    # DPDP Act consent evidence — captured at opt-in, immutable audit trail.
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # active | opted_out | blocked
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_table_label: Mapped[str | None] = mapped_column(String(40), nullable=True)

    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..5
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional link to a CRM Lead so guests flow into pipelines/campaigns.
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    vouchers: Mapped[list["RestaurantVoucher"]] = relationship(
        "RestaurantVoucher", back_populates="guest")


class RestaurantVoucher(BaseModel):
    """A single-use complimentary voucher. `code` is a strong, non-enumerable
    secret shown to the guest on WhatsApp and burned by staff at redemption.

    Redemption is an ATOMIC conditional UPDATE (see RestaurantService.redeem):
    only a row still in 'active' can transition to 'redeemed', so a double-scan
    or race can never burn the same voucher twice."""
    __tablename__ = "restaurant_vouchers"
    __table_args__ = (
        UniqueConstraint("code", name="uq_restaurant_voucher_code"),
        Index("ix_restaurant_voucher_org_status", "organization_id", "status"),
        Index("ix_restaurant_voucher_guest", "guest_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurant_venues.id", ondelete="SET NULL"), nullable=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurant_offers.id", ondelete="RESTRICT"), nullable=False)
    guest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurant_guests.id", ondelete="CASCADE"), nullable=False)

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    offer_title: Mapped[str] = mapped_column(String(160), nullable=False)  # snapshot at issue

    # active | redeemed | expired | void
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    issued_table_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    redeemed_table_label: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # WhatsApp delivery bookkeeping (message id from the outbox, best-effort).
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|sent|simulated|failed
    wa_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"), nullable=True)

    guest: Mapped[RestaurantGuest] = relationship("RestaurantGuest", back_populates="vouchers")

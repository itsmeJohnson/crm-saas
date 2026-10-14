"""Pydantic v2 schemas for the Restaurant QR-Voucher vertical."""
from __future__ import annotations

import uuid
from datetime import datetime, date

from pydantic import BaseModel, Field, ConfigDict


# ============================= Public (unauthenticated) =============================

class PublicScanContext(BaseModel):
    venue: dict
    table: dict
    offer: dict


class PublicOptInRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=20)
    email: str | None = Field(default=None, max_length=160)
    dob: str | None = Field(default=None, max_length=20)
    marketing_consent: bool = False


# ============================= Venues =============================

class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(default=None, max_length=80)
    timezone: str = "Asia/Kolkata"
    default_country_code: str = "91"
    logo_url: str | None = None
    brand_color: str = "#D97706"
    consent_text: str | None = None
    whatsapp_settings_id: uuid.UUID | None = None


class VenueUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    timezone: str | None = None
    default_country_code: str | None = None
    logo_url: str | None = None
    brand_color: str | None = None
    consent_text: str | None = None
    whatsapp_settings_id: uuid.UUID | None = None
    default_offer_id: uuid.UUID | None = None
    is_active: bool | None = None


class VenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    default_country_code: str
    logo_url: str | None
    brand_color: str
    consent_text: str
    whatsapp_settings_id: uuid.UUID | None
    default_offer_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


# ============================= Offers =============================

class OfferCreate(BaseModel):
    venue_id: uuid.UUID
    title: str = Field(min_length=2, max_length=160)
    description: str | None = None
    terms: str | None = None
    image_url: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    voucher_validity_days: int | None = Field(default=30, ge=1, le=3650)
    per_guest_limit: int = Field(default=1, ge=1, le=50)
    total_issue_limit: int | None = Field(default=None, ge=1)


class OfferUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    description: str | None = None
    terms: str | None = None
    image_url: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    voucher_validity_days: int | None = Field(default=None, ge=1, le=3650)
    per_guest_limit: int | None = Field(default=None, ge=1, le=50)
    total_issue_limit: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venue_id: uuid.UUID
    title: str
    description: str | None
    terms: str | None
    image_url: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    voucher_validity_days: int | None
    per_guest_limit: int
    total_issue_limit: int | None
    issued_count: int
    redeemed_count: int
    is_active: bool


# ============================= Tables =============================

class TableCreate(BaseModel):
    venue_id: uuid.UUID
    label: str = Field(min_length=1, max_length=40)
    offer_id: uuid.UUID | None = None


class TableBulkCreate(BaseModel):
    venue_id: uuid.UUID
    prefix: str = Field(default="T-", max_length=20)
    start: int = Field(default=1, ge=1)
    count: int = Field(ge=1, le=200)
    offer_id: uuid.UUID | None = None


class TableUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=40)
    offer_id: uuid.UUID | None = None
    is_active: bool | None = None


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venue_id: uuid.UUID
    label: str
    token: str
    offer_id: uuid.UUID | None
    is_active: bool
    scan_count: int
    last_scanned_at: datetime | None
    scan_url: str | None = None


# ============================= Guests & Vouchers =============================

class GuestResponse(BaseModel):
    """Phone/email/dob are masked or omitted by the API for non-privileged roles."""
    id: uuid.UUID
    name: str
    phone: str          # masked unless caller is privileged
    email: str | None
    dob: date | None
    status: str
    marketing_consent: bool
    visit_count: int
    last_visit_at: datetime | None
    last_table_label: str | None
    rating: int | None
    created_at: datetime


class VoucherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    offer_title: str
    status: str
    issued_table_label: str | None
    expires_at: datetime | None
    redeemed_at: datetime | None
    redeemed_table_label: str | None
    delivery_status: str
    created_at: datetime


# ============================= Redemption =============================

class RedeemRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    table_label: str | None = Field(default=None, max_length=40)


class StatsResponse(BaseModel):
    total_guests: int
    active_opted_in: int
    opted_out: int
    total_visits: int
    total_vouchers: int
    active_vouchers: int
    redeemed_vouchers: int
    redemption_rate_pct: int
    birthdays_this_month: int


# ============================= Campaigns =============================

class CampaignPreview(BaseModel):
    recipients: int
    suppressed_opted_out: int
    est_cost: float
    cost_per_msg: float


class CampaignSendRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1024)
    title: str | None = Field(default=None, max_length=160)
    venue_id: uuid.UUID | None = None


class CampaignResult(BaseModel):
    title: str
    recipients: int
    queued: int
    simulated: int
    channel: str
    est_cost: float

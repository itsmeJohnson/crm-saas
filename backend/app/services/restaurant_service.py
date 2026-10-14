"""Restaurant QR-Voucher vertical — business logic & security core.

This service is where every security-relevant rule the demo lacked is enforced:

* Tenant identity is resolved server-side from the venue slug + table token —
  never trusted from client input.
* Voucher codes are strong and non-enumerable (32^8 keyspace).
* Redemption is an ATOMIC conditional UPDATE, so a double-scan/race cannot burn
  the same voucher twice.
* Public opt-in is throttled per-phone and enforces explicit DPDP consent, with
  the consent text/ip/timestamp snapshotted onto the guest row.
* PII (phone/email/dob) never leaves an authenticated staff endpoint, and is
  masked for non-admin roles by the API layer.
"""
from __future__ import annotations

import re
import secrets
import uuid
import logging
from datetime import datetime, timezone, timedelta, date

from fastapi import HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.restaurant import (
    RestaurantVenue, RestaurantOffer, RestaurantTable,
    RestaurantGuest, RestaurantVoucher,
)
from app.models.whatsapp import WhatsAppSettings, WhatsAppMessage
from app.services.audit_service import AuditService

logger = logging.getLogger("app.restaurant")

# Voucher code alphabet: no ambiguous 0/O/1/I/L so staff can key it by hand.
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LEN = 8

# Public opt-in throttle: at most this many opt-in *attempts* per phone per window.
OPTIN_MAX_PER_PHONE = 5
OPTIN_WINDOW = timedelta(hours=1)

PRIVILEGED_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
STAFF_ROLES = ("SuperAdmin", "OrgAdmin", "Manager", "Employee")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime (SQLite has no tz) to UTC-aware so it can
    be compared safely against _now() on any backend."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s[:60] or "venue"


def normalize_phone(raw: str | None, country_code: str = "91") -> str:
    """Return an E.164-ish string WITHOUT the leading '+', e.g. '919880194821'.

    Accepts messy input ('+91 98801-94821', '098801 94821', '9880194821') and a
    tenant default country code. Raises 400 on anything that can't be a mobile.
    """
    digits = re.sub(r"\D", "", str(raw or ""))
    cc = re.sub(r"\D", "", country_code or "91") or "91"

    if not digits:
        raise HTTPException(status_code=400, detail="A valid WhatsApp mobile number is required.")

    # Strip a single leading trunk 0 (common in IN local dialing).
    if len(digits) > 10 and digits.startswith("0"):
        digits = digits.lstrip("0")

    if digits.startswith(cc) and len(digits) == len(cc) + 10:
        national = digits[len(cc):]
    elif len(digits) == 10:
        national = digits
    elif len(digits) > 10:
        # Assume the last 10 are the subscriber number for the default region.
        national = digits[-10:]
    else:
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit mobile number.")

    if not re.fullmatch(r"[1-9]\d{9}", national):
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit mobile number.")

    return f"{cc}{national}"


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    tail = phone[-4:]
    return f"{'•' * max(0, len(phone) - 4)}{tail}"


class RestaurantService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ========================= helpers =========================

    async def _generate_code(self, prefix: str) -> str:
        prefix = re.sub(r"[^A-Z0-9]", "", (prefix or "SMOKE").upper())[:6] or "OFFER"
        for _ in range(25):
            body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
            code = f"{prefix}-{body}"
            exists = (await self.db.execute(
                select(RestaurantVoucher.id).filter(RestaurantVoucher.code == code)
            )).first()
            if not exists:
                return code
        # Astronomically unlikely; widen with entropy rather than fail the guest.
        return f"{prefix}-{secrets.token_hex(6).upper()}"

    async def _resolve_system_actor(self, organization_id: uuid.UUID) -> User | None:
        """A user to attribute background WhatsApp sends to (the outbox worker
        requires a created_by). Prefer an OrgAdmin, else any active user."""
        for role in ("OrgAdmin", "Manager"):
            u = (await self.db.execute(select(User).filter(
                User.organization_id == organization_id, User.role == role,
                User.is_active == True, User.is_deleted == False).limit(1))).scalars().first()
            if u:
                return u
        return (await self.db.execute(select(User).filter(
            User.organization_id == organization_id,
            User.is_active == True, User.is_deleted == False).limit(1))).scalars().first()

    # ========================= public: scan context =========================

    async def get_scan_context(self, venue_slug: str, table_token: str) -> dict:
        """Resolve tenant + offer for a scanned QR. Public-safe (no PII).
        This is the ONLY place the public flow learns the restaurant identity."""
        venue = (await self.db.execute(select(RestaurantVenue).filter(
            RestaurantVenue.slug == venue_slug,
            RestaurantVenue.is_active == True,
            RestaurantVenue.is_deleted == False,
        ))).scalars().first()
        if not venue:
            raise HTTPException(status_code=404, detail="This QR code is not active.")

        table = (await self.db.execute(select(RestaurantTable).filter(
            RestaurantTable.token == table_token,
            RestaurantTable.venue_id == venue.id,
            RestaurantTable.is_deleted == False,
        ))).scalars().first()
        if not table or not table.is_active:
            raise HTTPException(status_code=404, detail="This table QR is not active.")

        offer = await self._active_offer_for_table(venue, table)
        if not offer:
            raise HTTPException(status_code=409, detail="No active offer is available right now.")

        return {
            "venue": {
                "name": venue.name, "slug": venue.slug,
                "logo_url": venue.logo_url, "brand_color": venue.brand_color,
                "consent_text": venue.consent_text,
            },
            "table": {"label": table.label, "token": table.token},
            "offer": {
                "title": offer.title, "description": offer.description,
                "terms": offer.terms, "image_url": offer.image_url,
            },
        }

    async def _active_offer_for_table(self, venue: RestaurantVenue,
                                      table: RestaurantTable) -> RestaurantOffer | None:
        offer_id = table.offer_id or venue.default_offer_id
        if not offer_id:
            return None
        offer = await self.db.get(RestaurantOffer, offer_id)
        if not offer or offer.is_deleted or not offer.is_active:
            return None
        now = _now()
        if offer.valid_from and _aware(offer.valid_from) > now:
            return None
        if offer.valid_until and _aware(offer.valid_until) < now:
            return None
        return offer

    # ========================= public: opt-in =========================

    async def opt_in(self, *, venue_slug: str, table_token: str, name: str,
                     phone: str, email: str | None, dob: str | None,
                     marketing_consent: bool, consent_ip: str | None) -> dict:
        name = (name or "").strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="Please enter your name.")
        if len(name) > 120:
            name = name[:120]
        if not marketing_consent:
            raise HTTPException(
                status_code=400,
                detail="Consent is required to send your voucher on WhatsApp.")

        venue = (await self.db.execute(select(RestaurantVenue).filter(
            RestaurantVenue.slug == venue_slug,
            RestaurantVenue.is_active == True,
            RestaurantVenue.is_deleted == False,
        ))).scalars().first()
        if not venue:
            raise HTTPException(status_code=404, detail="This QR code is not active.")

        table = (await self.db.execute(select(RestaurantTable).filter(
            RestaurantTable.token == table_token,
            RestaurantTable.venue_id == venue.id,
            RestaurantTable.is_deleted == False,
        ))).scalars().first()
        if not table or not table.is_active:
            raise HTTPException(status_code=404, detail="This table QR is not active.")

        offer = await self._active_offer_for_table(venue, table)
        if not offer:
            raise HTTPException(status_code=409, detail="No active offer is available right now.")

        norm_phone = normalize_phone(phone, venue.default_country_code)
        parsed_dob = self._parse_dob(dob)

        # ---- Per-phone throttle (blunts spam / WhatsApp cost abuse / enumeration) ----
        recent = (await self.db.execute(select(func.count(RestaurantVoucher.id)).filter(
            RestaurantVoucher.organization_id == venue.organization_id,
            RestaurantVoucher.created_at >= _now() - OPTIN_WINDOW,
            RestaurantVoucher.guest_id.in_(
                select(RestaurantGuest.id).filter(
                    RestaurantGuest.organization_id == venue.organization_id,
                    RestaurantGuest.phone == norm_phone,
                )),
        ))).scalar() or 0
        if recent >= OPTIN_MAX_PER_PHONE:
            raise HTTPException(
                status_code=429,
                detail="You've requested several vouchers recently. Please try again later.")

        guest, is_new = await self._upsert_guest(
            venue=venue, table=table, name=name, phone=norm_phone,
            email=email, dob=parsed_dob, consent_ip=consent_ip)

        voucher, is_existing = await self._issue_voucher(venue, offer, guest, table)

        # Table scan analytics (best-effort).
        table.scan_count = (table.scan_count or 0) + 1
        table.last_scanned_at = _now()

        await self.db.flush()

        # WhatsApp delivery — best effort, never blocks the guest's confirmation.
        try:
            await self._deliver_voucher(venue, guest, voucher)
        except Exception as e:  # noqa: BLE001
            logger.warning("Voucher WhatsApp delivery failed (org=%s): %s",
                           venue.organization_id, e)

        await self.db.commit()

        return {
            "is_new_guest": is_new,
            "already_had_voucher": is_existing,
            "guest": {"name": guest.name, "phone_masked": mask_phone(guest.phone),
                      "visit_count": guest.visit_count},
            "voucher": {"code": voucher.code, "offer_title": voucher.offer_title,
                        "status": voucher.status, "expires_at": voucher.expires_at,
                        "delivery_status": voucher.delivery_status},
            "message": ("Welcome! Your voucher is on its way to WhatsApp."
                        if is_new else
                        f"Welcome back, {guest.name.split(' ')[0]}! (Visit #{guest.visit_count})"),
        }

    def _parse_dob(self, dob: str | None) -> date | None:
        if not dob:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                d = datetime.strptime(dob.strip(), fmt).date()
                if d.year < 1900 or d > date.today():
                    return None
                return d
            except ValueError:
                continue
        return None

    async def _upsert_guest(self, *, venue, table, name, phone, email, dob,
                            consent_ip) -> tuple[RestaurantGuest, bool]:
        existing = (await self.db.execute(select(RestaurantGuest).filter(
            RestaurantGuest.organization_id == venue.organization_id,
            RestaurantGuest.phone == phone,
        ))).scalars().first()

        now = _now()
        if existing:
            existing.name = name or existing.name
            existing.email = email or existing.email
            existing.dob = dob or existing.dob
            existing.visit_count = (existing.visit_count or 1) + 1
            existing.last_visit_at = now
            existing.last_table_label = table.label
            existing.venue_id = venue.id
            # Re-affirm consent (guest opted in again).
            if existing.status == "opted_out":
                existing.status = "active"
                existing.opted_out_at = None
            existing.marketing_consent = True
            existing.consent_text = venue.consent_text
            existing.consent_ip = consent_ip
            existing.consent_at = now
            return existing, False

        guest = RestaurantGuest(
            organization_id=venue.organization_id, venue_id=venue.id,
            name=name, phone=phone, email=email, dob=dob,
            marketing_consent=True, consent_text=venue.consent_text,
            consent_ip=consent_ip, consent_at=now,
            status="active", visit_count=1, last_visit_at=now,
            last_table_label=table.label,
        )
        self.db.add(guest)
        await self.db.flush()
        return guest, True

    async def _issue_voucher(self, venue, offer, guest, table) -> tuple[RestaurantVoucher, bool]:
        # Dedup: reuse an existing active, unexpired voucher for this offer.
        active = (await self.db.execute(select(RestaurantVoucher).filter(
            RestaurantVoucher.guest_id == guest.id,
            RestaurantVoucher.offer_id == offer.id,
            RestaurantVoucher.status == "active",
        ).order_by(RestaurantVoucher.created_at.desc()))).scalars().first()
        if active and (not active.expires_at or _aware(active.expires_at) > _now()):
            return active, True

        # Enforce per-guest active limit and global issue cap.
        active_count = (await self.db.execute(select(func.count(RestaurantVoucher.id)).filter(
            RestaurantVoucher.guest_id == guest.id,
            RestaurantVoucher.offer_id == offer.id,
            RestaurantVoucher.status == "active",
        ))).scalar() or 0
        if active_count >= (offer.per_guest_limit or 1):
            # Already at limit but none reusable (expired) — return the newest anyway.
            if active:
                return active, True
        if offer.total_issue_limit is not None and (offer.issued_count or 0) >= offer.total_issue_limit:
            raise HTTPException(status_code=409, detail="This offer has reached its limit.")

        expires_at = None
        if offer.voucher_validity_days:
            expires_at = _now() + timedelta(days=offer.voucher_validity_days)

        code = await self._generate_code(offer.title.split(" ")[0] if offer.title else venue.slug)
        voucher = RestaurantVoucher(
            organization_id=venue.organization_id, venue_id=venue.id,
            offer_id=offer.id, guest_id=guest.id, code=code,
            offer_title=offer.title, status="active",
            issued_table_label=table.label, expires_at=expires_at,
            delivery_status="pending",
        )
        self.db.add(voucher)
        offer.issued_count = (offer.issued_count or 0) + 1
        await self.db.flush()
        return voucher, False

    # ========================= WhatsApp delivery =========================

    async def _resolve_wa_settings(self, organization_id: uuid.UUID,
                                   preferred_id: uuid.UUID | None = None) -> WhatsAppSettings | None:
        if preferred_id:
            s = await self.db.get(WhatsAppSettings, preferred_id)
            if s and not s.is_deleted:
                return s
        return (await self.db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == organization_id,
            WhatsAppSettings.is_active == True,
            WhatsAppSettings.is_deleted == False,
        ).order_by(WhatsAppSettings.is_default.desc()))).scalars().first()

    async def _enqueue_whatsapp_text(self, *, organization_id, settings_row, actor,
                                     phone, body, display_name) -> WhatsAppMessage | None:
        """Create an OUTBOUND outbox message and enqueue it via the shared WhatsApp
        outbox worker. Returns the message, or None when no WABA/actor is configured
        (caller treats that as 'simulated')."""
        if not settings_row or not actor:
            logger.info("[SIMULATED WhatsApp] to=%s body=%.40s", phone, body)
            return None
        from app.services.whatsapp_service import WhatsAppService
        from app.services.queue_service import QueueService
        wa = WhatsAppService(self.db)
        conv = await wa._get_or_create_conversation(  # noqa: SLF001 (intentional reuse)
            organization_id, phone, settings_row.id, display_name=display_name)
        msg = WhatsAppMessage(
            organization_id=organization_id, conversation_id=conv.id,
            direction="OUTBOUND", body=body, wa_status="queued", media_type="text",
        )
        self.db.add(msg)
        await self.db.flush()
        await QueueService(self.db).enqueue(
            organization_id=organization_id, job_type="send_whatsapp",
            payload={"message_id": str(msg.id)}, created_by=actor.id)
        return msg

    async def _deliver_voucher(self, venue: RestaurantVenue, guest: RestaurantGuest,
                               voucher: RestaurantVoucher) -> None:
        """Deliver the voucher over WhatsApp. Degrades to 'simulated' when no
        WABA/owner is configured so the product is demoable before go-live."""
        settings_row = await self._resolve_wa_settings(venue.organization_id, venue.whatsapp_settings_id)
        actor = await self._resolve_system_actor(venue.organization_id)
        body = (f"Hi {guest.name.split(' ')[0]}! 🎉 Your {voucher.offer_title} at "
                f"{venue.name} is ready.\n\nShow this code to our team to redeem:\n"
                f"*{voucher.code}*\n\nReply STOP to opt out anytime.")
        msg = await self._enqueue_whatsapp_text(
            organization_id=venue.organization_id, settings_row=settings_row, actor=actor,
            phone=guest.phone, body=body, display_name=guest.name)
        if msg is None:
            voucher.delivery_status = "simulated"
        else:
            voucher.wa_message_id = msg.id
            voucher.delivery_status = "sent"

    # ========================= campaigns & opt-out =========================

    MARKETING_MSG_COST = 0.85  # ₹ per Meta marketing message (India), for owner cost preview

    async def _opted_in_guests(self, organization_id, venue_id=None) -> list[RestaurantGuest]:
        q = select(RestaurantGuest).filter(
            RestaurantGuest.organization_id == organization_id,
            RestaurantGuest.is_deleted == False,
            RestaurantGuest.status == "active",
            RestaurantGuest.marketing_consent == True,
        )
        if venue_id:
            q = q.filter(RestaurantGuest.venue_id == venue_id)
        return list((await self.db.execute(q)).scalars().all())

    async def campaign_preview(self, actor: User, venue_id: uuid.UUID | None = None) -> dict:
        if venue_id:
            await self._get_venue(actor, venue_id)  # tenant check
        recipients = len(await self._opted_in_guests(actor.organization_id, venue_id))
        suppressed = (await self.db.execute(select(func.count(RestaurantGuest.id)).filter(
            RestaurantGuest.organization_id == actor.organization_id,
            RestaurantGuest.is_deleted == False,
            RestaurantGuest.status == "opted_out",
        ))).scalar() or 0
        return {
            "recipients": recipients,
            "suppressed_opted_out": suppressed,
            "est_cost": round(recipients * self.MARKETING_MSG_COST, 2),
            "cost_per_msg": self.MARKETING_MSG_COST,
        }

    async def send_campaign(self, actor: User, *, message: str, title: str | None,
                            venue_id: uuid.UUID | None = None) -> dict:
        message = (message or "").strip()
        if len(message) < 3:
            raise HTTPException(status_code=400, detail="Message is too short.")
        if len(message) > 1024:
            raise HTTPException(status_code=400, detail="Message is too long (max 1024 chars).")

        venue = await self._get_venue(actor, venue_id) if venue_id else None
        guests = await self._opted_in_guests(actor.organization_id, venue_id)
        if not guests:
            raise HTTPException(status_code=409, detail="No opted-in guests to message yet.")

        settings_row = await self._resolve_wa_settings(
            actor.organization_id, venue.whatsapp_settings_id if venue else None)
        # Opt-out footer is mandatory for Meta marketing templates.
        body = message if "STOP" in message.upper() else f"{message}\n\nReply STOP to opt out."

        queued = simulated = 0
        for g in guests:
            try:
                msg = await self._enqueue_whatsapp_text(
                    organization_id=actor.organization_id, settings_row=settings_row, actor=actor,
                    phone=g.phone, body=body.replace("{name}", g.name.split(" ")[0]),
                    display_name=g.name)
                if msg is None:
                    simulated += 1
                else:
                    queued += 1
            except Exception as e:  # noqa: BLE001 — one bad recipient must not fail the blast
                logger.warning("Campaign send failed for guest %s: %s", g.id, e)

        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="RESTAURANT_CAMPAIGN_SENT", resource_type="RestaurantCampaign",
            resource_id=str(venue_id) if venue_id else None,
            action_metadata={"title": title, "recipients": len(guests),
                             "queued": queued, "simulated": simulated})
        await self.db.commit()
        return {
            "title": title or "Campaign",
            "recipients": len(guests),
            "queued": queued,
            "simulated": simulated,
            "channel": "whatsapp" if settings_row else "simulated",
            "est_cost": round(len(guests) * self.MARKETING_MSG_COST, 2),
        }

    async def apply_inbound_optout(self, organization_id: uuid.UUID, phone: str, body: str) -> str | None:
        """Called from the WhatsApp inbound webhook. Flips a restaurant guest's
        marketing status when they reply STOP / START. Returns the action taken."""
        text = (body or "").strip().upper()
        STOP = {"STOP", "UNSUBSCRIBE", "CANCEL", "OPTOUT", "OPT-OUT", "OPT OUT"}
        START = {"START", "UNSTOP", "SUBSCRIBE", "RESUME", "OPTIN", "OPT-IN", "OPT IN"}
        action = "opted_out" if text in STOP else "active" if text in START else None
        if action is None:
            return None
        last10 = re.sub(r"\D", "", phone or "")[-10:]
        if not last10:
            return None
        guest = (await self.db.execute(select(RestaurantGuest).filter(
            RestaurantGuest.organization_id == organization_id,
            RestaurantGuest.is_deleted == False,
            RestaurantGuest.phone.like(f"%{last10}"),
        ))).scalars().first()
        if not guest:
            return None
        guest.status = action
        guest.opted_out_at = _now() if action == "opted_out" else None
        if action == "active":
            guest.marketing_consent = True
        await self.db.flush()
        logger.info("[Restaurant opt-%s] org=%s phone=%s", "out" if action == "opted_out" else "in", organization_id, last10)
        return action

    # ========================= staff: redeem (atomic) =========================

    async def redeem(self, *, actor: User, code: str, table_label: str | None) -> dict:
        """Burn a voucher. ATOMIC: the UPDATE only matches a voucher still in
        'active' within the actor's tenant, so a race/double-scan can flip the
        row exactly once. rowcount == 0 means it was already used / invalid."""
        code = (code or "").strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="Enter a voucher code.")

        voucher = (await self.db.execute(select(RestaurantVoucher).filter(
            func.upper(RestaurantVoucher.code) == code,
            RestaurantVoucher.organization_id == actor.organization_id,
        ))).scalars().first()

        if not voucher:
            # Do not reveal whether the code exists in another tenant.
            raise HTTPException(status_code=404, detail="Voucher not found.")

        # Lazy-expire.
        if voucher.status == "active" and voucher.expires_at and _aware(voucher.expires_at) < _now():
            voucher.status = "expired"
            await self.db.commit()

        if voucher.status == "redeemed":
            raise HTTPException(
                status_code=409,
                detail=(f"Already redeemed on "
                        f"{voucher.redeemed_at.strftime('%d %b %Y, %I:%M %p') if voucher.redeemed_at else 'earlier'}."))
        if voucher.status == "expired":
            raise HTTPException(status_code=409, detail="This voucher has expired.")
        if voucher.status == "void":
            raise HTTPException(status_code=409, detail="This voucher is no longer valid.")

        now = _now()
        result = await self.db.execute(
            update(RestaurantVoucher)
            .where(
                RestaurantVoucher.id == voucher.id,
                RestaurantVoucher.organization_id == actor.organization_id,
                RestaurantVoucher.status == "active",  # <-- the atomic guard
            )
            .values(status="redeemed", redeemed_at=now,
                    redeemed_by_user_id=actor.id,
                    redeemed_table_label=(table_label or None))
        )
        if result.rowcount == 0:
            # Someone else burned it between our read and write.
            raise HTTPException(status_code=409, detail="This voucher was just redeemed.")

        await self.db.execute(
            update(RestaurantOffer)
            .where(RestaurantOffer.id == voucher.offer_id)
            .values(redeemed_count=RestaurantOffer.redeemed_count + 1))

        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="RESTAURANT_VOUCHER_REDEEMED", resource_type="RestaurantVoucher",
            resource_id=str(voucher.id),
            action_metadata={"code": voucher.code, "offer": voucher.offer_title,
                             "table": table_label})
        await self.db.commit()

        await self.db.refresh(voucher)
        return {
            "success": True,
            "message": f"Redeemed: {voucher.offer_title}",
            "voucher": {"code": voucher.code, "offer_title": voucher.offer_title,
                        "status": voucher.status, "redeemed_at": voucher.redeemed_at,
                        "redeemed_by": actor.first_name or actor.email},
        }

    async def lookup_for_staff(self, *, actor: User, code: str) -> dict:
        """Authenticated preview before burning (staff scanner). No PII beyond a
        masked confirmation name; used to show 'valid / used / expired'."""
        code = (code or "").strip().upper()
        voucher = (await self.db.execute(select(RestaurantVoucher).filter(
            func.upper(RestaurantVoucher.code) == code,
            RestaurantVoucher.organization_id == actor.organization_id,
        ))).scalars().first()
        if not voucher:
            raise HTTPException(status_code=404, detail="Voucher not found.")
        guest = await self.db.get(RestaurantGuest, voucher.guest_id)
        status_now = voucher.status
        if status_now == "active" and voucher.expires_at and _aware(voucher.expires_at) < _now():
            status_now = "expired"
        return {
            "code": voucher.code, "offer_title": voucher.offer_title,
            "status": status_now, "expires_at": voucher.expires_at,
            "redeemed_at": voucher.redeemed_at,
            "guest_name": guest.name if guest else None,
            "guest_phone_masked": mask_phone(guest.phone) if guest else None,
            "redeemable": status_now == "active",
        }

    # ========================= admin: venues =========================

    async def _unique_slug(self, base: str) -> str:
        candidate = _slugify(base)
        n = 1
        while True:
            exists = (await self.db.execute(select(RestaurantVenue.id).filter(
                RestaurantVenue.slug == candidate))).first()
            if not exists:
                return candidate
            n += 1
            candidate = f"{_slugify(base)}-{n}"

    async def create_venue(self, actor: User, data: dict) -> RestaurantVenue:
        slug = await self._unique_slug(data.get("slug") or data["name"])
        venue = RestaurantVenue(
            organization_id=actor.organization_id, name=data["name"], slug=slug,
            timezone=data.get("timezone") or "Asia/Kolkata",
            default_country_code=re.sub(r"\D", "", data.get("default_country_code") or "91") or "91",
            logo_url=data.get("logo_url"),
            brand_color=data.get("brand_color") or "#D97706",
            whatsapp_settings_id=data.get("whatsapp_settings_id"),
        )
        if data.get("consent_text"):
            venue.consent_text = data["consent_text"]
        self.db.add(venue)
        await self.db.commit()
        await self.db.refresh(venue)
        return venue

    async def list_venues(self, actor: User) -> list[RestaurantVenue]:
        return list((await self.db.execute(select(RestaurantVenue).filter(
            RestaurantVenue.organization_id == actor.organization_id,
            RestaurantVenue.is_deleted == False,
        ).order_by(RestaurantVenue.created_at.desc()))).scalars().all())

    async def _get_venue(self, actor: User, venue_id: uuid.UUID) -> RestaurantVenue:
        v = await self.db.get(RestaurantVenue, venue_id)
        if not v or v.is_deleted or v.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Venue not found.")
        return v

    async def update_venue(self, actor: User, venue_id: uuid.UUID, data: dict) -> RestaurantVenue:
        v = await self._get_venue(actor, venue_id)
        if data.get("default_offer_id"):
            await self._get_offer(actor, data["default_offer_id"])  # tenant check
        for field in ("name", "timezone", "logo_url", "brand_color", "consent_text",
                      "whatsapp_settings_id", "default_offer_id", "is_active"):
            if field in data and data[field] is not None:
                setattr(v, field, data[field])
        if data.get("default_country_code"):
            v.default_country_code = re.sub(r"\D", "", data["default_country_code"]) or v.default_country_code
        await self.db.commit()
        await self.db.refresh(v)
        return v

    # ========================= admin: offers =========================

    async def create_offer(self, actor: User, data: dict) -> RestaurantOffer:
        venue = await self._get_venue(actor, data["venue_id"])
        offer = RestaurantOffer(
            organization_id=actor.organization_id, venue_id=venue.id,
            title=data["title"], description=data.get("description"),
            terms=data.get("terms"), image_url=data.get("image_url"),
            valid_from=data.get("valid_from"), valid_until=data.get("valid_until"),
            voucher_validity_days=data.get("voucher_validity_days", 30),
            per_guest_limit=data.get("per_guest_limit", 1),
            total_issue_limit=data.get("total_issue_limit"),
        )
        self.db.add(offer)
        await self.db.flush()
        # First offer becomes the venue default automatically.
        if not venue.default_offer_id:
            venue.default_offer_id = offer.id
        await self.db.commit()
        await self.db.refresh(offer)
        return offer

    async def list_offers(self, actor: User, venue_id: uuid.UUID | None = None) -> list[RestaurantOffer]:
        q = select(RestaurantOffer).filter(
            RestaurantOffer.organization_id == actor.organization_id,
            RestaurantOffer.is_deleted == False)
        if venue_id:
            q = q.filter(RestaurantOffer.venue_id == venue_id)
        return list((await self.db.execute(q.order_by(RestaurantOffer.created_at.desc()))).scalars().all())

    async def _get_offer(self, actor: User, offer_id: uuid.UUID) -> RestaurantOffer:
        o = await self.db.get(RestaurantOffer, offer_id)
        if not o or o.is_deleted or o.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Offer not found.")
        return o

    async def update_offer(self, actor: User, offer_id: uuid.UUID, data: dict) -> RestaurantOffer:
        o = await self._get_offer(actor, offer_id)
        for field, value in data.items():
            if value is not None and hasattr(o, field):
                setattr(o, field, value)
        await self.db.commit()
        await self.db.refresh(o)
        return o

    # ========================= admin: tables + QR =========================

    async def create_table(self, actor: User, data: dict) -> RestaurantTable:
        venue = await self._get_venue(actor, data["venue_id"])
        if data.get("offer_id"):
            await self._get_offer(actor, data["offer_id"])
        table = self._new_table(actor, venue, data["label"], data.get("offer_id"))
        self.db.add(table)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail="A table with that label already exists.")
        await self.db.refresh(table)
        return table

    async def bulk_create_tables(self, actor: User, data: dict) -> list[RestaurantTable]:
        venue = await self._get_venue(actor, data["venue_id"])
        if data.get("offer_id"):
            await self._get_offer(actor, data["offer_id"])
        existing = {t.label for t in (await self.db.execute(select(RestaurantTable).filter(
            RestaurantTable.venue_id == venue.id, RestaurantTable.is_deleted == False))).scalars().all()}
        created = []
        for i in range(data["count"]):
            label = f"{data.get('prefix', 'T-')}{data['start'] + i}"
            if label in existing:
                continue
            t = self._new_table(actor, venue, label, data.get("offer_id"))
            self.db.add(t)
            created.append(t)
        await self.db.commit()
        for t in created:
            await self.db.refresh(t)
        return created

    def _new_table(self, actor, venue, label, offer_id) -> RestaurantTable:
        return RestaurantTable(
            organization_id=actor.organization_id, venue_id=venue.id,
            label=str(label).strip()[:40], token=secrets.token_urlsafe(18),
            offer_id=offer_id)

    async def list_tables(self, actor: User, venue_id: uuid.UUID | None = None) -> list[RestaurantTable]:
        q = select(RestaurantTable).filter(
            RestaurantTable.organization_id == actor.organization_id,
            RestaurantTable.is_deleted == False)
        if venue_id:
            q = q.filter(RestaurantTable.venue_id == venue_id)
        return list((await self.db.execute(q.order_by(RestaurantTable.label))).scalars().all())

    async def update_table(self, actor: User, table_id: uuid.UUID, data: dict) -> RestaurantTable:
        t = await self.db.get(RestaurantTable, table_id)
        if not t or t.is_deleted or t.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Table not found.")
        if data.get("offer_id"):
            await self._get_offer(actor, data["offer_id"])
        for field in ("label", "offer_id", "is_active"):
            if field in data and data[field] is not None:
                setattr(t, field, data[field])
        await self.db.commit()
        await self.db.refresh(t)
        return t

    async def scan_url_for(self, table: RestaurantTable) -> str:
        from app.core.config import settings
        base = (settings.FRONTEND_URL or "").rstrip("/")
        venue = await self.db.get(RestaurantVenue, table.venue_id)
        slug = venue.slug if venue else ""
        return f"{base}/r/{slug}/t/{table.token}"

    # ========================= admin: guests / vouchers / stats =========================

    async def list_guests(self, actor: User, *, venue_id: uuid.UUID | None = None,
                          search: str | None = None, limit: int = 100,
                          offset: int = 0) -> list[RestaurantGuest]:
        q = select(RestaurantGuest).filter(
            RestaurantGuest.organization_id == actor.organization_id,
            RestaurantGuest.is_deleted == False)
        if venue_id:
            q = q.filter(RestaurantGuest.venue_id == venue_id)
        if search:
            like = f"%{search.strip()}%"
            q = q.filter((RestaurantGuest.name.ilike(like)) | (RestaurantGuest.phone.ilike(like)))
        q = q.order_by(RestaurantGuest.created_at.desc()).limit(min(limit, 500)).offset(offset)
        return list((await self.db.execute(q)).scalars().all())

    async def list_vouchers(self, actor: User, *, status_filter: str | None = None,
                            limit: int = 100, offset: int = 0) -> list[RestaurantVoucher]:
        q = select(RestaurantVoucher).filter(
            RestaurantVoucher.organization_id == actor.organization_id,
            RestaurantVoucher.is_deleted == False)
        if status_filter:
            q = q.filter(RestaurantVoucher.status == status_filter)
        q = q.order_by(RestaurantVoucher.created_at.desc()).limit(min(limit, 500)).offset(offset)
        return list((await self.db.execute(q)).scalars().all())

    async def stats(self, actor: User) -> dict:
        org = actor.organization_id

        async def _count(model, *conds):
            base = [model.organization_id == org, model.is_deleted == False, *conds]
            return (await self.db.execute(select(func.count(model.id)).filter(*base))).scalar() or 0

        total_guests = await _count(RestaurantGuest)
        active_opted_in = await _count(RestaurantGuest, RestaurantGuest.status == "active",
                                       RestaurantGuest.marketing_consent == True)
        opted_out = await _count(RestaurantGuest, RestaurantGuest.status == "opted_out")
        total_visits = (await self.db.execute(select(func.coalesce(func.sum(RestaurantGuest.visit_count), 0)).filter(
            RestaurantGuest.organization_id == org, RestaurantGuest.is_deleted == False))).scalar() or 0
        total_vouchers = await _count(RestaurantVoucher)
        active_vouchers = await _count(RestaurantVoucher, RestaurantVoucher.status == "active")
        redeemed_vouchers = await _count(RestaurantVoucher, RestaurantVoucher.status == "redeemed")

        month = _now().month
        birthdays = (await self.db.execute(select(func.count(RestaurantGuest.id)).filter(
            RestaurantGuest.organization_id == org, RestaurantGuest.is_deleted == False,
            RestaurantGuest.dob.isnot(None),
            func.extract("month", RestaurantGuest.dob) == month))).scalar() or 0

        return {
            "total_guests": total_guests, "active_opted_in": active_opted_in,
            "opted_out": opted_out, "total_visits": int(total_visits),
            "total_vouchers": total_vouchers, "active_vouchers": active_vouchers,
            "redeemed_vouchers": redeemed_vouchers,
            "redemption_rate_pct": round((redeemed_vouchers / total_vouchers) * 100) if total_vouchers else 0,
            "birthdays_this_month": birthdays,
        }

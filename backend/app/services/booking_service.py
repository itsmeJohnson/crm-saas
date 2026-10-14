"""Self-service appointment booking (Feature 14).

A BookingLink exposes a host's open slots to the public. Availability is derived
from the org's working hours, minus existing calendar events (busy) and holidays,
sliced into fixed-length slots. Booking a slot creates an Appointment calendar
event for the host and an inbound Lead (so the host is alerted the moment it lands).

Timezone note: working hours are expressed in the org's configured timezone;
slots are generated in that zone and persisted as timezone-aware UTC instants.
"""
import re
import uuid
import secrets
from datetime import datetime, timedelta, date, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.booking import BookingLink
from app.models.calendar_event import CalendarEvent, WorkingHoursConfig, Holiday
from app.services.calendar_service import DEFAULT_DAYS
from app.services.lead_service import LeadService

_DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
_MAX_RANGE_DAYS = 62


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _parse_hhmm(s: str) -> time:
    h, m = (s or "09:00").split(":")
    return time(int(h), int(m))


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------------- admin CRUD ----------------
    async def _slugify(self, base: str) -> str:
        root = re.sub(r"[^a-z0-9]+", "-", (base or "book").lower()).strip("-")[:40] or "book"
        for _ in range(5):
            candidate = f"{root}-{secrets.token_hex(3)}"
            exists = (await self.db.execute(select(BookingLink.id).filter(BookingLink.slug == candidate))).first()
            if not exists:
                return candidate
        return f"book-{secrets.token_hex(6)}"

    async def create_link(self, actor: User, data: dict) -> BookingLink:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins/managers manage booking links")
        host_id = data.get("host_user_id") or actor.id
        host = (await self.db.execute(select(User).filter(
            User.id == host_id, User.organization_id == actor.organization_id,
            User.is_active == True, User.is_deleted == False))).scalars().first()
        if not host:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host user not found in your organization")
        slot = int(data.get("slot_minutes") or 30)
        if slot < 5 or slot > 480:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_minutes must be between 5 and 480")
        link = BookingLink(
            organization_id=actor.organization_id, host_user_id=host.id,
            slug=await self._slugify(data.get("title") or host.first_name or "book"),
            title=(data.get("title") or "Book a meeting")[:150],
            description=data.get("description"), location=data.get("location"),
            slot_minutes=slot, buffer_minutes=max(0, int(data.get("buffer_minutes") or 0)),
            advance_days=min(120, max(1, int(data.get("advance_days") or 14))),
            is_active=data.get("is_active", True), created_by=actor.id,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def list_links(self, actor: User) -> list[BookingLink]:
        q = select(BookingLink).filter(
            BookingLink.organization_id == actor.organization_id, BookingLink.is_deleted == False)
        if not self._privileged(actor):
            q = q.filter(BookingLink.host_user_id == actor.id)
        return list((await self.db.execute(q.order_by(BookingLink.created_at.desc()))).scalars().all())

    async def _owned(self, actor: User, link_id: uuid.UUID) -> BookingLink:
        link = (await self.db.execute(select(BookingLink).filter(
            BookingLink.id == link_id, BookingLink.organization_id == actor.organization_id,
            BookingLink.is_deleted == False))).scalars().first()
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking link not found")
        if not self._privileged(actor) and link.host_user_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking link")
        return link

    async def update_link(self, actor: User, link_id: uuid.UUID, data: dict) -> BookingLink:
        link = await self._owned(actor, link_id)
        for f in ("title", "description", "location", "is_active"):
            if f in data and data[f] is not None:
                setattr(link, f, data[f])
        if data.get("slot_minutes"):
            s = int(data["slot_minutes"])
            if s < 5 or s > 480:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_minutes must be between 5 and 480")
            link.slot_minutes = s
        if data.get("buffer_minutes") is not None:
            link.buffer_minutes = max(0, int(data["buffer_minutes"]))
        if data.get("advance_days"):
            link.advance_days = min(120, max(1, int(data["advance_days"])))
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def delete_link(self, actor: User, link_id: uuid.UUID) -> None:
        link = await self._owned(actor, link_id)
        link.is_deleted = True
        self.db.add(link)
        await self.db.flush()

    # ---------------- public read ----------------
    async def _public_link(self, slug: str) -> BookingLink:
        link = (await self.db.execute(select(BookingLink).filter(
            BookingLink.slug == slug, BookingLink.is_active == True,
            BookingLink.is_deleted == False))).scalars().first()
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking page not found")
        return link

    async def public_get(self, slug: str) -> dict:
        link = await self._public_link(slug)
        host = await self.db.get(User, link.host_user_id)
        host_name = f"{host.first_name or ''} {host.last_name or ''}".strip() if host else "Our team"
        return {
            "slug": link.slug, "title": link.title, "description": link.description,
            "location": link.location, "slot_minutes": link.slot_minutes,
            "advance_days": link.advance_days, "host_name": host_name or "Our team",
        }

    async def _working_hours(self, org_id: uuid.UUID) -> tuple[dict, ZoneInfo]:
        cfg = (await self.db.execute(select(WorkingHoursConfig).filter(
            WorkingHoursConfig.organization_id == org_id))).scalars().first()
        days = (cfg.days if cfg and cfg.days else dict(DEFAULT_DAYS))
        return days, _tz(cfg.timezone if cfg else "UTC")

    async def _holidays(self, org_id: uuid.UUID) -> set[tuple[int, int, date]]:
        rows = (await self.db.execute(select(Holiday).filter(
            Holiday.organization_id == org_id, Holiday.is_deleted == False))).scalars().all()
        exact = {h.holiday_date for h in rows if not h.recurring_annual}
        annual = {(h.holiday_date.month, h.holiday_date.day) for h in rows if h.recurring_annual}
        return exact, annual

    async def _busy(self, host_id: uuid.UUID, org_id: uuid.UUID, lo: datetime, hi: datetime) -> list[tuple[datetime, datetime]]:
        rows = (await self.db.execute(select(CalendarEvent).filter(
            CalendarEvent.organization_id == org_id,
            CalendarEvent.assigned_user_id == host_id,
            CalendarEvent.is_deleted == False,
            CalendarEvent.status != "Cancelled",
            CalendarEvent.start_at < hi, CalendarEvent.end_at > lo))).scalars().all()
        out = []
        for ev in rows:
            s = ev.start_at if ev.start_at.tzinfo else ev.start_at.replace(tzinfo=timezone.utc)
            e = ev.end_at if ev.end_at.tzinfo else ev.end_at.replace(tzinfo=timezone.utc)
            out.append((s, e))
        return out

    async def availability(self, slug: str, date_from: date, date_to: date) -> dict:
        link = await self._public_link(slug)
        days, tz = await self._working_hours(link.organization_id)
        exact_hol, annual_hol = await self._holidays(link.organization_id)

        now = datetime.now(timezone.utc)
        min_day = now.astimezone(tz).date()
        max_day = (now.astimezone(tz) + timedelta(days=link.advance_days)).date()
        start_day = max(date_from, min_day)
        end_day = min(date_to, max_day)
        if (end_day - start_day).days > _MAX_RANGE_DAYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date range too large")

        # One busy scan across the whole window, then filter per slot.
        window_lo = datetime.combine(start_day, time(0, 0), tzinfo=tz).astimezone(timezone.utc)
        window_hi = datetime.combine(end_day + timedelta(days=1), time(0, 0), tzinfo=tz).astimezone(timezone.utc)
        busy = await self._busy(link.host_user_id, link.organization_id, window_lo, window_hi)
        step = timedelta(minutes=link.slot_minutes + link.buffer_minutes)
        dur = timedelta(minutes=link.slot_minutes)

        result_days: list[dict] = []
        d = start_day
        while d <= end_day:
            cfg = days.get(_DOW[d.weekday()], {})
            is_holiday = d in exact_hol or (d.month, d.day) in annual_hol
            slots: list[str] = []
            if cfg.get("enabled") and not is_holiday:
                day_start = datetime.combine(d, _parse_hhmm(cfg.get("start", "09:00")), tzinfo=tz)
                day_end = datetime.combine(d, _parse_hhmm(cfg.get("end", "17:00")), tzinfo=tz)
                cur = day_start
                while cur + dur <= day_end:
                    s_utc = cur.astimezone(timezone.utc)
                    e_utc = (cur + dur).astimezone(timezone.utc)
                    if s_utc >= now and not any(s_utc < b_e and e_utc > b_s for b_s, b_e in busy):
                        slots.append(s_utc.isoformat())
                    cur += step
            result_days.append({"date": d.isoformat(), "slots": slots})
            d += timedelta(days=1)
        return {"slug": link.slug, "slot_minutes": link.slot_minutes, "timezone": str(tz), "days": result_days}

    # ---------------- public booking ----------------
    async def book(self, slug: str, data: dict) -> dict:
        link = await self._public_link(slug)
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip() or None
        phone = (data.get("phone") or "").strip() or None
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your name is required")
        if not email and not phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An email or phone is required")

        try:
            start = datetime.fromisoformat(str(data.get("slot_start")))
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slot_start (expected ISO 8601)")
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start = start.astimezone(timezone.utc)
        end = start + timedelta(minutes=link.slot_minutes)

        now = datetime.now(timezone.utc)
        if start < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That time is in the past")
        if start > now + timedelta(days=link.advance_days + 1):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That time is outside the booking window")

        # Re-validate the slot is still genuinely open (working hours + not busy).
        _, tz = await self._working_hours(link.organization_id)
        day = start.astimezone(tz).date()
        avail = await self.availability(slug, day, day)
        open_starts = {s for dd in avail["days"] for s in dd["slots"]}
        if start.isoformat() not in open_starts:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That slot is no longer available")

        host = await self.db.get(User, link.host_user_id)
        if not host or not host.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Host is unavailable")

        # Create an inbound lead so the host is alerted the moment it lands.
        fn, _, ln = name.partition(" ")
        lead_service = LeadService(self.db, link.organization_id)
        lead = await lead_service.create_lead(host, {
            "first_name": fn or None, "last_name": ln or fn or "Guest",
            "email": email, "phone": phone,
            "title": f"Appointment: {link.title}"[:255],
            "source": f"Booking: {link.title}"[:100],
            "assigned_user_id": host.id,
        }, inbound=True)

        event = CalendarEvent(
            organization_id=link.organization_id, title=f"{link.title} — {name}"[:255],
            description=data.get("notes"), event_type="Appointment", location=link.location,
            start_at=start, end_at=end, status="Scheduled",
            assigned_user_id=host.id, created_by=host.id,
            attendees=[{"name": name, "email": email}],
            lead_id=lead.id, remind_at=start - timedelta(minutes=30),
        )
        self.db.add(event)
        link.bookings_count = (link.bookings_count or 0) + 1
        self.db.add(link)
        await self.db.flush()

        # Booking an appointment IS the "site visit scheduled" step — auto-advance
        # the lead into a matching stage if the org has one. Routing the move
        # through update_lead fires the lead_updated workflow, so any
        # "on Site Visit Scheduled → send confirmation email" rule runs too.
        try:
            from app.models.pipeline import PipelineStage
            from sqlalchemy import func as _func
            svc_stage = (await self.db.execute(select(PipelineStage.id).where(
                PipelineStage.organization_id == link.organization_id,
                PipelineStage.is_deleted == False,
                _func.lower(PipelineStage.name).like("%site visit%"),
            ).limit(1))).scalars().first()
            if svc_stage and lead.stage_id != svc_stage:
                await lead_service.update_lead(host, lead.id, {"stage_id": svc_stage})
        except Exception:
            pass

        await self.db.refresh(event)
        return {"status": "confirmed", "event_id": str(event.id), "lead_id": str(lead.id),
                "start": start.isoformat(), "end": end.isoformat(), "host_name": f"{host.first_name} {host.last_name}".strip()}

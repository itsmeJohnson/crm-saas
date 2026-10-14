"""Feature 14 — self-service appointment booking.

Availability derives from org working hours minus busy events; booking a slot
creates an Appointment event + inbound Lead and blocks the slot from re-booking.
"""
import uuid
from datetime import datetime, timedelta, timezone, date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.calendar_event import CalendarEvent
from app.models.lead import Lead
from app.models.notification import Notification
from app.services.booking_service import BookingService


async def _seed(db: AsyncSession, slug: str):
    org = await OrganizationRepository(db).create({"name": slug, "slug": slug})
    await db.commit()
    host = await UserRepository(db).create_user(org.id, {
        "email": f"host@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Hana", "last_name": "Host", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    return org, host


def _first_open(avail):
    for d in avail["days"]:
        if d["slots"]:
            return d["slots"][0]
    return None


@pytest.mark.asyncio
async def test_create_link_and_availability_and_book(db: AsyncSession):
    org, host = await _seed(db, "book-a")
    svc = BookingService(db)
    link = await svc.create_link(host, {"title": "Sales Demo", "slot_minutes": 30})
    await db.commit()
    assert link.slug

    today = datetime.now(timezone.utc).date()
    avail = await svc.availability(link.slug, today, today + timedelta(days=10))
    slot = _first_open(avail)
    assert slot, "expected at least one open weekday slot within 10 days"

    res = await svc.book(link.slug, {"slot_start": slot, "name": "Guest Person", "email": "g@x.com"})
    await db.commit()
    assert res["status"] == "confirmed"

    # An Appointment event and an inbound lead were created for the host.
    ev = (await db.execute(select(CalendarEvent).filter(CalendarEvent.id == uuid.UUID(res["event_id"])))).scalar_one()
    assert ev.event_type == "Appointment" and ev.assigned_user_id == host.id and ev.lead_id is not None
    lead = (await db.execute(select(Lead).filter(Lead.id == uuid.UUID(res["lead_id"])))).scalar_one()
    assert lead.source.startswith("Booking:")
    # Host was alerted (inbound lead notification).
    notifs = (await db.execute(select(Notification).filter(
        Notification.user_id == host.id, Notification.category == "lead"))).scalars().all()
    assert len(notifs) == 1


@pytest.mark.asyncio
async def test_double_book_same_slot_conflicts(db: AsyncSession):
    org, host = await _seed(db, "book-b")
    svc = BookingService(db)
    link = await svc.create_link(host, {"title": "Intro", "slot_minutes": 30})
    await db.commit()
    today = datetime.now(timezone.utc).date()
    slot = _first_open(await svc.availability(link.slug, today, today + timedelta(days=10)))
    await svc.book(link.slug, {"slot_start": slot, "name": "First", "phone": "+911"})
    await db.commit()

    # Same slot is now busy → excluded from availability and rejected on booking.
    avail2 = await svc.availability(link.slug, today, today + timedelta(days=10))
    assert slot not in {s for d in avail2["days"] for s in d["slots"]}
    with pytest.raises(HTTPException) as ei:
        await svc.book(link.slug, {"slot_start": slot, "name": "Second", "phone": "+912"})
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_book_past_slot_rejected(db: AsyncSession):
    org, host = await _seed(db, "book-c")
    svc = BookingService(db)
    link = await svc.create_link(host, {"title": "X"})
    await db.commit()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with pytest.raises(HTTPException) as ei:
        await svc.book(link.slug, {"slot_start": past, "name": "Late", "phone": "+913"})
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_employee_cannot_create_link(db: AsyncSession):
    org, host = await _seed(db, "book-d")
    emp = await UserRepository(db).create_user(org.id, {
        "email": "emp@book-d.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ed", "last_name": "Emp", "role": "Employee", "is_active": True})
    await db.commit()
    with pytest.raises(HTTPException) as ei:
        await BookingService(db).create_link(emp, {"title": "Nope"})
    assert ei.value.status_code == 403

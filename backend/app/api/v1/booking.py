import uuid
from datetime import date
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.booking_service import BookingService
from app.schemas.booking import (
    BookingLinkCreate, BookingLinkUpdate, BookingLinkResponse, PublicBookRequest,
)

# Tenant router (authenticated). Public router has NO auth — visitors book here.
router = APIRouter()
public_router = APIRouter()


@router.get("/links", response_model=List[BookingLinkResponse])
async def list_booking_links(actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).list_links(actor)


@router.post("/links", response_model=BookingLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_link(req: BookingLinkCreate,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).create_link(actor, req.model_dump(exclude_unset=True))


@router.patch("/links/{link_id}", response_model=BookingLinkResponse)
async def update_booking_link(link_id: uuid.UUID, req: BookingLinkUpdate,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).update_link(actor, link_id, req.model_dump(exclude_unset=True))


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking_link(link_id: uuid.UUID,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    await BookingService(db).delete_link(actor, link_id)


# ---------- Appointments API (authenticated) ----------
@router.get("/appointments")
async def list_appointments(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.services.calendar_service import CalendarService
    events = await CalendarService(db).list_events(actor)
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "start_at": e.start_at.isoformat() if e.start_at else None,
            "end_at": e.end_at.isoformat() if e.end_at else None,
            "status": e.status or "Confirmed",
            "location": e.location,
            "event_type": e.event_type
        }
        for e in events
    ]


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    req: dict,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.services.calendar_service import CalendarService
    from datetime import datetime, timezone, timedelta

    title = req.get("title") or "Appointment Slot"
    start_at_val = req.get("start_at") or req.get("scheduled_at")
    if isinstance(start_at_val, str):
        try:
            start_at_dt = datetime.fromisoformat(start_at_val.replace("Z", "+00:00"))
        except Exception:
            start_at_dt = datetime.now(timezone.utc)
    else:
        start_at_dt = datetime.now(timezone.utc)

    end_at_val = req.get("end_at")
    if isinstance(end_at_val, str):
        try:
            end_at_dt = datetime.fromisoformat(end_at_val.replace("Z", "+00:00"))
        except Exception:
            end_at_dt = start_at_dt + timedelta(minutes=45)
    else:
        end_at_dt = start_at_dt + timedelta(minutes=45)

    ev = await CalendarService(db).create_event(actor, {
        "title": title,
        "description": req.get("description"),
        "event_type": "Appointment",
        "location": req.get("location") or "Main Operatory",
        "start_at": start_at_dt,
        "end_at": end_at_dt,
        "status": req.get("status") or "Confirmed",
        "allow_conflict": True,
        "assigned_user_id": req.get("assigned_user_id") or actor.id,
        "contact_id": req.get("contact_id")
    })
    return {
        "id": str(ev.id),
        "title": ev.title,
        "description": ev.description,
        "scheduled_at": ev.start_at.isoformat() if ev.start_at else None,
        "start_at": ev.start_at.isoformat() if ev.start_at else None,
        "end_at": ev.end_at.isoformat() if ev.end_at else None,
        "status": ev.status or "Confirmed",
    }



# ---------------- public (no auth) ----------------
@public_router.get("/{slug}")
async def public_booking_page(slug: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).public_get(slug)


@public_router.get("/{slug}/availability")
async def public_availability(slug: str, db: Annotated[AsyncSession, Depends(get_db)],
                              date_from: date = Query(...), date_to: date = Query(...)):
    return await BookingService(db).availability(slug, date_from, date_to)


@public_router.post("/{slug}/book", status_code=status.HTTP_201_CREATED)
async def public_book(slug: str, req: PublicBookRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).book(slug, req.model_dump())

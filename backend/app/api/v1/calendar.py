import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.calendar import (
    EventCreate, EventUpdate, EventResponse, CalendarItem,
    HolidayCreate, HolidayResponse, WorkingHoursUpdate, WorkingHoursResponse,
    FeedUrlResponse, CalendarReportResponse,
)
from app.services.calendar_service import CalendarService
from app.middleware.permissions import require_active_user, require_role

_oa_or_mgr = require_role(["OrgAdmin", "Manager"])
router = APIRouter()


# ---------- Public iCal feed (token auth, no bearer — external calendars subscribe) ----------
@router.get("/feed/{token}.ics")
async def calendar_ics_feed(token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """Read-only iCalendar feed. Subscribe from Google/Outlook/Apple Calendar with this URL."""
    ics = await CalendarService(db).build_ics_for_token(token)
    if ics is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="Not found")
    return Response(content=ics, media_type="text/calendar",
                    headers={"Content-Disposition": "inline; filename=crm-calendar.ics"})


@router.get("/feed-url", response_model=FeedUrlResponse)
async def calendar_feed_url(request: Request, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get (or create) your personal .ics subscription URL."""
    token = await CalendarService(db).get_or_create_feed_token(actor)
    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}/api/v1/calendar/feed/{token}.ics", "token": token}


# ---------- Unified calendar ----------
@router.get("/", response_model=List[CalendarItem])
async def unified_calendar(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime = Query(...), date_to: datetime = Query(...), types: str | None = Query(None),
):
    """All calendar items in a range: events, tasks, activity meetings/appointments, lead follow-ups, holidays."""
    type_set = {t.strip() for t in types.split(",") if t.strip()} if types else None
    return await CalendarService(db).unified(actor, date_from, date_to, types=type_set)


@router.get("/reports", response_model=CalendarReportResponse)
async def calendar_reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).get_report(actor)


# ---------- Working hours (OrgAdmin/Manager) ----------
@router.get("/working-hours", response_model=WorkingHoursResponse)
async def get_working_hours(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).get_working_hours(actor)


@router.patch("/working-hours", response_model=WorkingHoursResponse)
async def update_working_hours(req: WorkingHoursUpdate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).update_working_hours(actor, req.model_dump(exclude_unset=True))


# ---------- Holidays ----------
@router.get("/holidays", response_model=List[HolidayResponse])
async def list_holidays(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await CalendarService(db).list_holidays(actor))


@router.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(req: HolidayCreate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).create_holiday(actor, req.model_dump())


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(holiday_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CalendarService(db).delete_holiday(actor, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Events CRUD ----------
@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(req: EventCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).create_event(actor, req.model_dump())


@router.get("/events", response_model=List[EventResponse])
async def list_events(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
):
    return list(await CalendarService(db).list_events(actor, date_from=date_from, date_to=date_to))


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).get_event(actor, event_id)


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(event_id: uuid.UUID, req: EventUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CalendarService(db).update_event(actor, event_id, req.model_dump(exclude_unset=True))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CalendarService(db).delete_event(actor, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

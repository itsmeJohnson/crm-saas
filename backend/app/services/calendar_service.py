import uuid
import secrets
from datetime import datetime, timezone, date, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.calendar_event import CalendarEvent, Holiday, WorkingHoursConfig
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

DEFAULT_DAYS = {
    "mon": {"enabled": True, "start": "09:00", "end": "17:00"},
    "tue": {"enabled": True, "start": "09:00", "end": "17:00"},
    "wed": {"enabled": True, "start": "09:00", "end": "17:00"},
    "thu": {"enabled": True, "start": "09:00", "end": "17:00"},
    "fri": {"enabled": True, "start": "09:00", "end": "17:00"},
    "sat": {"enabled": False, "start": "09:00", "end": "17:00"},
    "sun": {"enabled": False, "start": "09:00", "end": "17:00"},
}


def _aware(dt):
    """Normalize a datetime to tz-aware UTC (SQLite returns naive for timezone columns)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _advance(dt: datetime, recurrence: str, n: int = 1):
    if recurrence == "daily":
        return dt + timedelta(days=n)
    if recurrence == "weekly":
        return dt + timedelta(weeks=n)
    if recurrence == "monthly":
        month = dt.month - 1 + n
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(dt.day, 28)
        return dt.replace(year=year, month=month, day=day)
    return dt


def expand_occurrences(ev: CalendarEvent, range_from: datetime, range_to: datetime) -> list[tuple[datetime, datetime]]:
    """Return (start, end) pairs for an event's occurrences overlapping [range_from, range_to]."""
    start_at = _aware(ev.start_at)
    end_at = _aware(ev.end_at)
    range_from = _aware(range_from)
    range_to = _aware(range_to)
    duration = end_at - start_at
    if ev.recurrence == "none" or not ev.recurrence:
        if end_at >= range_from and start_at <= range_to:
            return [(start_at, end_at)]
        return []
    out = []
    cur = start_at
    until = None
    if ev.recurrence_until:
        until = datetime.combine(ev.recurrence_until, datetime.max.time()).replace(tzinfo=timezone.utc)
    hard_cap = range_to + timedelta(days=1)
    guard = 0
    while cur <= hard_cap and guard < 1000:
        guard += 1
        if until and cur > until:
            break
        occ_end = cur + duration
        if occ_end >= range_from and cur <= range_to:
            out.append((cur, occ_end))
        cur = _advance(cur, ev.recurrence)
    return out


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _is_privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------- Events ----------
    async def _get_event(self, actor: User, event_id: uuid.UUID) -> CalendarEvent:
        res = await self.db.execute(select(CalendarEvent).filter(
            CalendarEvent.id == event_id, CalendarEvent.organization_id == actor.organization_id, CalendarEvent.is_deleted == False))
        ev = res.scalars().first()
        if not ev:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if not self._is_privileged(actor) and ev.assigned_user_id != actor.id and ev.created_by != actor.id:
            attendee_ids = {str(a.get("user_id")) for a in (ev.attendees or []) if a.get("user_id")}
            if str(actor.id) not in attendee_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        return ev

    async def _notify_event(self, actor: User, ev: CalendarEvent, verb: str) -> None:
        recipients = set()
        if ev.assigned_user_id and ev.assigned_user_id != actor.id:
            recipients.add(ev.assigned_user_id)
        for a in (ev.attendees or []):
            uid = a.get("user_id")
            if uid:
                try:
                    u = uuid.UUID(str(uid))
                    if u != actor.id:
                        recipients.add(u)
                except ValueError:
                    pass
        for uid in recipients:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=uid, category="calendar",
                title=f"Event {verb}", body=f'"{ev.title}" on {ev.start_at.strftime("%b %d, %H:%M")}',
                link_url=f"/calendar?eventId={ev.id}", action_metadata={"event_id": str(ev.id)})

    async def create_event(self, actor: User, data: dict) -> CalendarEvent:
        if data["end_at"] < data["start_at"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_at must be after start_at")
        if data.get("assigned_user_id"):
            from app.repositories.user_repository import UserRepository
            u = await UserRepository(self.db).get_user_by_id(actor.organization_id, data["assigned_user_id"])
            if not u or not u.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user not found or inactive")
        ev = CalendarEvent(
            organization_id=actor.organization_id,
            title=data["title"], description=data.get("description"), event_type=data.get("event_type", "Meeting"),
            location=data.get("location"), start_at=data["start_at"], end_at=data["end_at"], all_day=data.get("all_day", False),
            assigned_user_id=data.get("assigned_user_id") or actor.id, created_by=actor.id, attendees=data.get("attendees"),
            lead_id=data.get("lead_id"), contact_id=data.get("contact_id"), company_id=data.get("company_id"),
            recurrence=data.get("recurrence", "none"), recurrence_until=data.get("recurrence_until"),
            remind_at=data.get("remind_at"),
        )
        self.db.add(ev)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="EVENT_CREATED", resource_type="calendar_event", resource_id=str(ev.id),
                                   action_metadata={"title": ev.title})
        await self._notify_event(actor, ev, "invited")
        await self.db.refresh(ev)
        return ev

    async def list_events(self, actor: User, date_from=None, date_to=None) -> list[CalendarEvent]:
        q = select(CalendarEvent).filter(CalendarEvent.organization_id == actor.organization_id, CalendarEvent.is_deleted == False)
        if not self._is_privileged(actor):
            q = q.filter(or_(CalendarEvent.assigned_user_id == actor.id, CalendarEvent.created_by == actor.id))
        # for recurring, we can't range-filter on start alone; fetch and expand at call site
        if date_to is not None:
            q = q.filter(CalendarEvent.start_at <= date_to)
        q = q.order_by(CalendarEvent.start_at.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_event(self, actor: User, event_id: uuid.UUID) -> CalendarEvent:
        return await self._get_event(actor, event_id)

    async def update_event(self, actor: User, event_id: uuid.UUID, data: dict) -> CalendarEvent:
        ev = await self._get_event(actor, event_id)
        for k, v in data.items():
            setattr(ev, k, v)
        if ev.end_at < ev.start_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_at must be after start_at")
        self.db.add(ev)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="EVENT_UPDATED", resource_type="calendar_event", resource_id=str(event_id))
        await self.db.refresh(ev)
        return ev

    async def delete_event(self, actor: User, event_id: uuid.UUID) -> None:
        ev = await self._get_event(actor, event_id)
        ev.is_deleted = True
        ev.deleted_at = datetime.now(timezone.utc)
        self.db.add(ev)
        await self.db.flush()

    # ---------- Unified calendar ----------
    async def unified(self, actor: User, date_from: datetime, date_to: datetime, types: set[str] | None = None) -> list[dict]:
        from app.models.task import Task
        from app.models.activity import Activity
        from app.models.lead import Lead
        org = actor.organization_id
        items: list[dict] = []

        # 1. Events (with recurrence expansion)
        events = await self.list_events(actor, date_to=date_to)
        for ev in events:
            for (s, e) in expand_occurrences(ev, date_from, date_to):
                items.append({"source": "event", "type": ev.event_type.lower(), "id": str(ev.id),
                              "title": ev.title, "start": s, "end": e, "all_day": ev.all_day, "status": ev.status,
                              "link": f"/calendar?eventId={ev.id}",
                              "metadata": {"location": ev.location, "recurring": ev.recurrence != "none"}})

        # 2. Tasks (due dates)
        tq = select(Task).filter(Task.organization_id == org, Task.is_deleted == False,
                                 Task.due_date.isnot(None), Task.due_date >= date_from, Task.due_date <= date_to)
        if not self._is_privileged(actor):
            tq = tq.filter(or_(Task.assigned_user_id == actor.id, Task.created_by == actor.id))
        for t in (await self.db.execute(tq)).scalars().all():
            items.append({"source": "task", "type": "task", "id": str(t.id), "title": t.title,
                          "start": _aware(t.due_date), "end": _aware(t.due_date), "all_day": False, "status": t.status,
                          "link": f"/tasks?taskId={t.id}", "metadata": {"priority": t.priority}})

        # 3. Activity meetings/appointments/calls (due_date)
        aq = select(Activity).filter(Activity.organization_id == org, Activity.is_deleted == False,
                                     Activity.due_date.isnot(None), Activity.due_date >= date_from, Activity.due_date <= date_to,
                                     Activity.activity_type.in_(["Meeting", "Appointment", "Call"]))
        if not self._is_privileged(actor):
            aq = aq.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        for a in (await self.db.execute(aq)).scalars().all():
            items.append({"source": "activity", "type": a.activity_type.lower(), "id": str(a.id), "title": a.subject,
                          "start": _aware(a.due_date), "end": _aware(a.due_date), "all_day": False, "status": a.status,
                          "link": None, "metadata": {"activity_type": a.activity_type}})

        # 4. Lead follow-ups (available_at callbacks)
        lq = select(Lead).filter(Lead.organization_id == org, Lead.is_deleted == False,
                                 Lead.available_at.isnot(None), Lead.available_at >= date_from, Lead.available_at <= date_to)
        if not self._is_privileged(actor):
            lq = lq.filter(Lead.assigned_user_id == actor.id)
        for l in (await self.db.execute(lq)).scalars().all():
            items.append({"source": "followup", "type": "followup", "id": str(l.id), "title": f"Follow-up: {l.title}",
                          "start": l.available_at, "end": l.available_at, "all_day": False, "status": l.status,
                          "link": f"/leads?leadId={l.id}", "metadata": None})

        # 5. Holidays
        for h in await self._holidays_in_range(org, date_from.date(), date_to.date()):
            hs = datetime.combine(h["date"], datetime.min.time()).replace(tzinfo=timezone.utc)
            items.append({"source": "holiday", "type": "holiday", "id": h["id"], "title": h["name"],
                          "start": hs, "end": hs, "all_day": True, "status": None, "link": None, "metadata": None})

        if types:
            items = [i for i in items if i["type"] in types or i["source"] in types]
        items.sort(key=lambda i: i["start"])
        return items

    # ---------- Holidays ----------
    async def _holidays_in_range(self, org: uuid.UUID, d_from: date, d_to: date) -> list[dict]:
        res = await self.db.execute(select(Holiday).filter(Holiday.organization_id == org, Holiday.is_deleted == False))
        out = []
        for h in res.scalars().all():
            if h.recurring_annual:
                for yr in range(d_from.year, d_to.year + 1):
                    try:
                        occ = h.holiday_date.replace(year=yr)
                    except ValueError:
                        continue
                    if d_from <= occ <= d_to:
                        out.append({"id": str(h.id), "name": h.name, "date": occ})
            else:
                if d_from <= h.holiday_date <= d_to:
                    out.append({"id": str(h.id), "name": h.name, "date": h.holiday_date})
        return out

    async def create_holiday(self, actor: User, data: dict) -> Holiday:
        h = Holiday(organization_id=actor.organization_id, name=data["name"], holiday_date=data["holiday_date"],
                    recurring_annual=data.get("recurring_annual", False), created_by=actor.id)
        self.db.add(h)
        await self.db.flush()
        await self.db.refresh(h)
        return h

    async def list_holidays(self, actor: User) -> list[Holiday]:
        res = await self.db.execute(select(Holiday).filter(Holiday.organization_id == actor.organization_id, Holiday.is_deleted == False).order_by(Holiday.holiday_date.asc()))
        return list(res.scalars().all())

    async def delete_holiday(self, actor: User, holiday_id: uuid.UUID) -> None:
        res = await self.db.execute(select(Holiday).filter(Holiday.id == holiday_id, Holiday.organization_id == actor.organization_id, Holiday.is_deleted == False))
        h = res.scalars().first()
        if not h:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
        h.is_deleted = True
        self.db.add(h)
        await self.db.flush()

    # ---------- Working hours ----------
    async def get_working_hours(self, actor: User) -> WorkingHoursConfig:
        res = await self.db.execute(select(WorkingHoursConfig).filter(WorkingHoursConfig.organization_id == actor.organization_id))
        cfg = res.scalars().first()
        if not cfg:
            cfg = WorkingHoursConfig(organization_id=actor.organization_id, timezone="UTC", days=dict(DEFAULT_DAYS))
            self.db.add(cfg)
            await self.db.flush()
            await self.db.refresh(cfg)
        return cfg

    async def update_working_hours(self, actor: User, data: dict) -> WorkingHoursConfig:
        cfg = await self.get_working_hours(actor)
        if data.get("timezone"):
            cfg.timezone = data["timezone"]
        if data.get("days"):
            cfg.days = data["days"]
        self.db.add(cfg)
        await self.db.flush()
        await self.db.refresh(cfg)
        return cfg

    # ---------- iCal feed ----------
    async def get_or_create_feed_token(self, actor: User) -> str:
        res = await self.db.execute(select(User).filter(User.id == actor.id))
        user = res.scalars().first()
        if not user.calendar_feed_token:
            user.calendar_feed_token = secrets.token_urlsafe(24)
            self.db.add(user)
            await self.db.flush()
        return user.calendar_feed_token

    async def build_ics_for_token(self, token: str) -> str | None:
        res = await self.db.execute(select(User).filter(User.calendar_feed_token == token, User.is_active == True, User.is_deleted == False))
        user = res.scalars().first()
        if not user:
            return None
        now = datetime.now(timezone.utc)
        window_from = now - timedelta(days=30)
        window_to = now + timedelta(days=120)
        items = await self.unified(user, window_from, window_to)
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CRM//Calendar//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]

        def fmt(dt: datetime) -> str:
            return _aware(dt).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        def esc(s: str) -> str:
            return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

        for it in items:
            if it["source"] == "holiday":
                continue
            start = it["start"]
            end = it.get("end") or start
            lines += [
                "BEGIN:VEVENT",
                f"UID:{it['source']}-{it['id']}@crm",
                f"DTSTAMP:{fmt(now)}",
                f"DTSTART:{fmt(start)}",
                f"DTEND:{fmt(end)}",
                f"SUMMARY:{esc(it['title'])}",
                f"CATEGORIES:{esc(it['type'])}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    # ---------- Reminders (cron) ----------
    # (dispatched from lead_cron via dispatch_event_reminders)

    # ---------- Reports ----------
    async def get_report(self, actor: User) -> dict:
        from app.models.task import Task
        org = actor.organization_id
        now = datetime.now(timezone.utc)
        week = now + timedelta(days=7)

        def ev_base(*cols):
            q = select(*cols).filter(CalendarEvent.organization_id == org, CalendarEvent.is_deleted == False)
            if not self._is_privileged(actor):
                q = q.filter(or_(CalendarEvent.assigned_user_id == actor.id, CalendarEvent.created_by == actor.id))
            return q

        total = (await self.db.execute(ev_base(func.count(CalendarEvent.id)))).scalar() or 0
        upcoming = (await self.db.execute(ev_base(func.count(CalendarEvent.id)).filter(CalendarEvent.start_at >= now, CalendarEvent.start_at <= week))).scalar() or 0
        type_rows = (await self.db.execute(ev_base(CalendarEvent.event_type, func.count(CalendarEvent.id)).group_by(CalendarEvent.event_type))).all()

        from app.models.user import User as UserModel
        user_rows = (await self.db.execute(ev_base(CalendarEvent.assigned_user_id, func.count(CalendarEvent.id)).group_by(CalendarEvent.assigned_user_id))).all()
        uids = [r[0] for r in user_rows if r[0]]
        names = {}
        if uids:
            u = await self.db.execute(select(UserModel.id, UserModel.first_name, UserModel.last_name, UserModel.email).filter(UserModel.id.in_(uids)))
            for uid, fn, ln, em in u.all():
                names[uid] = f"{fn or ''} {ln or ''}".strip() or em

        tq = select(func.count(Task.id)).filter(Task.organization_id == org, Task.is_deleted == False,
                                                Task.due_date >= now, Task.due_date <= week, Task.status.in_(["Todo", "InProgress"]))
        if not self._is_privileged(actor):
            tq = tq.filter(or_(Task.assigned_user_id == actor.id, Task.created_by == actor.id))
        tasks_due = (await self.db.execute(tq)).scalar() or 0

        return {
            "total_events": total, "upcoming_7d": upcoming,
            "by_type": [{"label": r[0], "count": r[1]} for r in type_rows],
            "by_user": [{"label": names.get(r[0], "Unassigned") if r[0] else "Unassigned", "count": r[1]} for r in user_rows],
            "tasks_due_7d": tasks_due,
        }

"""Attendance Management service.

Covers the full daily cycle — clock in/out, breaks, worked-hours and late/early
computation against an assigned shift — plus shift definitions, shift
assignment, correction requests with manager approval, a live dashboard, and
monthly reports. Shift wall-clock times are interpreted in the organization's
timezone; all stored timestamps are tz-aware UTC.

Late/early are derived from the user's active shift on the work date. A
biometric device (or mobile app) can post punches through the same paths via
`source='biometric'`, so the module is integration-ready.
"""
from __future__ import annotations
import calendar as _cal
import uuid
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.organization import Organization
from app.models.attendance import (
    Shift, ShiftAssignment, AttendanceRecord, AttendanceBreak, AttendanceCorrection,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_WORKING_DAYS = ["mon", "tue", "wed", "thu", "fri"]
ATT_STATUSES = ("present", "absent", "late", "half_day", "on_leave", "holiday", "weekly_off")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    """Coerce a stored datetime to tz-aware UTC. Postgres returns tz-aware
    values for TIMESTAMPTZ columns, but SQLite (tests) returns naive ones —
    normalise before any arithmetic to avoid naive/aware subtraction errors."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _is_manager(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _can_admin(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    def _require_admin(self, actor: User):
        if not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only an OrgAdmin can manage shifts.")

    async def _downline_ids(self, actor: User) -> set[uuid.UUID]:
        """Users a manager may see: their recursive reporting downline + self."""
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return set(ids) | {actor.id}

    async def _assert_can_view_user(self, actor: User, user_id: uuid.UUID):
        if actor.id == user_id or self._can_admin(actor):
            return
        if actor.role == "Manager":
            if user_id in await self._downline_ids(actor):
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You cannot view this user's attendance.")

    # ---------- timezone helpers ----------
    async def _org_tz(self, org_id: uuid.UUID) -> ZoneInfo:
        tzname = (await self.db.execute(select(Organization.timezone).filter(
            Organization.id == org_id))).scalar() or "UTC"
        try:
            return ZoneInfo(tzname)
        except Exception:
            return ZoneInfo("UTC")

    async def _today(self, org_id: uuid.UUID) -> date:
        return _now().astimezone(await self._org_tz(org_id)).date()

    def _bounds(self, tz: ZoneInfo, work_date: date, shift: Shift) -> tuple[datetime, datetime]:
        """Expected start/end as tz-aware UTC datetimes for a shift on a date."""
        start = datetime.combine(work_date, shift.start_time, tzinfo=tz)
        end_date = work_date + timedelta(days=1) if shift.is_night_shift or shift.end_time <= shift.start_time else work_date
        end = datetime.combine(end_date, shift.end_time, tzinfo=tz)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    # ================= Shifts =================
    async def _get_shift(self, actor: User, shift_id: uuid.UUID) -> Shift:
        s = (await self.db.execute(select(Shift).filter(
            Shift.id == shift_id, Shift.organization_id == actor.organization_id,
            Shift.is_deleted == False))).scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
        return s

    async def _validate_shift_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(Shift.id).filter(Shift.organization_id == actor.organization_id,
                                    Shift.code == code, Shift.is_deleted == False)
        if exclude_id:
            q = q.filter(Shift.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Shift code '{code}' already exists.")

    @staticmethod
    def _parse_time(v) -> time:
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            parts = v.split(":")
            return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time value.")

    async def create_shift(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        await self._validate_shift_code(actor, data.get("code"))
        wd = data.get("working_days")
        if wd:
            bad = [d for d in wd if d not in WEEKDAYS]
            if bad:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid working_days: {bad}")
        start_t = self._parse_time(data["start_time"])
        end_t = self._parse_time(data["end_time"])
        s = Shift(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                  start_time=start_t, end_time=end_t,
                  break_minutes=int(data.get("break_minutes", 0)), grace_minutes=int(data.get("grace_minutes", 0)),
                  working_days=wd, is_night_shift=bool(data.get("is_night_shift", end_t <= start_t)),
                  status=data.get("status", "active"), color=data.get("color"), created_by=actor.id)
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SHIFT_CREATED", resource_type="shift", resource_id=str(s.id),
                                   action_metadata={"name": s.name})
        return self._serialize_shift(s)

    async def update_shift(self, actor: User, shift_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        s = await self._get_shift(actor, shift_id)
        if "code" in data:
            await self._validate_shift_code(actor, data.get("code"), exclude_id=s.id)
        for k in ("name", "code", "break_minutes", "grace_minutes", "working_days", "is_night_shift",
                  "status", "color"):
            if k in data:
                setattr(s, k, data[k])
        if "start_time" in data:
            s.start_time = self._parse_time(data["start_time"])
        if "end_time" in data:
            s.end_time = self._parse_time(data["end_time"])
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return self._serialize_shift(s)

    async def delete_shift(self, actor: User, shift_id: uuid.UUID) -> None:
        self._require_admin(actor)
        s = await self._get_shift(actor, shift_id)
        active = (await self.db.execute(select(func.count(ShiftAssignment.id)).filter(
            ShiftAssignment.shift_id == s.id, ShiftAssignment.is_deleted == False,
            or_(ShiftAssignment.end_date.is_(None), ShiftAssignment.end_date >= _now().date())))).scalar() or 0
        if active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{active} active assignment(s) use this shift. Reassign or end them first.")
        s.is_deleted = True
        self.db.add(s)
        await self.db.flush()

    async def list_shifts(self, actor: User, status_filter=None) -> list[dict]:
        q = select(Shift).filter(Shift.organization_id == actor.organization_id, Shift.is_deleted == False)
        if status_filter:
            q = q.filter(Shift.status == status_filter)
        rows = list((await self.db.execute(q.order_by(Shift.name.asc()))).scalars().all())
        return [self._serialize_shift(s) for s in rows]

    # ================= Shift assignment =================
    async def assign_shift(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        shift = await self._get_shift(actor, data["shift_id"])
        user_ids = data["user_ids"]
        start_date = data.get("start_date") or _now().date()
        end_date = data.get("end_date")
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().all())
        for u in users:
            # close any open-ended assignment that would overlap
            open_rows = list((await self.db.execute(select(ShiftAssignment).filter(
                ShiftAssignment.user_id == u.id, ShiftAssignment.organization_id == actor.organization_id,
                ShiftAssignment.is_deleted == False, ShiftAssignment.end_date.is_(None)))).scalars().all())
            for r in open_rows:
                if r.start_date < start_date:
                    r.end_date = start_date - timedelta(days=1)
                    self.db.add(r)
                else:
                    r.is_deleted = True
                    self.db.add(r)
            self.db.add(ShiftAssignment(organization_id=actor.organization_id, user_id=u.id, shift_id=shift.id,
                                        start_date=start_date, end_date=end_date, created_by=actor.id))
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=u.id, category="attendance",
                title="Shift assigned", body=f"You were assigned to the {shift.name} shift.",
                link_url="/attendance", action_metadata={"shift_id": str(shift.id)})
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SHIFT_ASSIGNED", resource_type="shift", resource_id=str(shift.id),
                                   action_metadata={"users": len(users)})
        return {"assigned": len(users)}

    async def _active_shift(self, org_id: uuid.UUID, user_id: uuid.UUID, on: date) -> Shift | None:
        # Delegate to the Shift Management resolver so clock-in/out honour both
        # direct assignments (unchanged behaviour) and rotations.
        from app.services.shift_service import ShiftService
        return await ShiftService(self.db).resolve_shift_for_user(org_id, user_id, on)

    async def user_assignments(self, actor: User, user_id: uuid.UUID) -> list[dict]:
        await self._assert_can_view_user(actor, user_id)
        rows = list((await self.db.execute(select(ShiftAssignment).filter(
            ShiftAssignment.organization_id == actor.organization_id, ShiftAssignment.user_id == user_id,
            ShiftAssignment.is_deleted == False).order_by(ShiftAssignment.start_date.desc()))).scalars().all())
        snames = await self._shift_names({r.shift_id for r in rows})
        return [{"id": str(r.id), "shift_id": str(r.shift_id), "shift_name": snames.get(r.shift_id),
                 "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat() if r.end_date else None}
                for r in rows]

    # ================= Clock in / out / break =================
    async def _record_for(self, org_id, user_id, work_date, *, create=False, created_by=None) -> AttendanceRecord | None:
        rec = (await self.db.execute(select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == org_id, AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date == work_date, AttendanceRecord.is_deleted == False))).scalars().first()
        if rec or not create:
            return rec
        rec = AttendanceRecord(organization_id=org_id, user_id=user_id, work_date=work_date,
                               status="present", created_by=created_by)
        self.db.add(rec)
        await self.db.flush()
        return rec

    async def clock_in(self, actor: User, *, target_user_id=None, latitude=None, longitude=None,
                       source="web", device_id=None, at: datetime | None = None) -> dict:
        user_id = target_user_id or actor.id
        if user_id != actor.id and not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot clock in for another user.")
        tz = await self._org_tz(actor.organization_id)
        now = (at or _now()).astimezone(timezone.utc)
        work_date = now.astimezone(tz).date()
        rec = await self._record_for(actor.organization_id, user_id, work_date, create=True, created_by=actor.id)
        if rec.clock_in_at and not rec.clock_out_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already clocked in.")
        if rec.clock_in_at and rec.clock_out_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attendance already completed for today.")
        shift = await self._active_shift(actor.organization_id, user_id, work_date)
        rec.clock_in_at = now
        rec.source = source
        rec.device_id = device_id
        rec.in_latitude = latitude
        rec.in_longitude = longitude
        rec.status = "present"
        rec.is_late = False
        rec.late_minutes = 0
        if shift:
            rec.shift_id = shift.id
            # Flexible (flexi-time) shifts have no fixed start, so late never applies.
            if not shift.is_flexible:
                start_utc, _ = self._bounds(tz, work_date, shift)
                allowed = start_utc + timedelta(minutes=shift.grace_minutes)
                if now > allowed:
                    rec.is_late = True
                    rec.late_minutes = int((now - start_utc).total_seconds() // 60)
                    rec.status = "late"
        self.db.add(rec)
        await self.db.flush()
        await self.db.refresh(rec)
        # Workflow: attendance marked (+ late_login when applicable)
        from app.services.workflow_service import WorkflowService
        wf = WorkflowService(self.db)
        await wf.run("attendance_marked", rec, actor, entity_type="attendance")
        if rec.is_late:
            await wf.run("late_login", rec, actor, entity_type="attendance")
            await self._notify_manager(actor, user_id,
                                       "Late login", f"{await self._name(user_id)} clocked in {rec.late_minutes} min late.")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ATTENDANCE_CLOCK_IN", resource_type="attendance", resource_id=str(rec.id),
                                   action_metadata={"user_id": str(user_id), "late": rec.is_late})
        return await self._serialize_record(rec)

    async def clock_out(self, actor: User, *, target_user_id=None, latitude=None, longitude=None,
                        at: datetime | None = None) -> dict:
        user_id = target_user_id or actor.id
        if user_id != actor.id and not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot clock out for another user.")
        tz = await self._org_tz(actor.organization_id)
        now = (at or _now()).astimezone(timezone.utc)
        work_date = now.astimezone(tz).date()
        rec = await self._record_for(actor.organization_id, user_id, work_date)
        if not rec or not rec.clock_in_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not clocked in yet.")
        if rec.clock_out_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already clocked out.")
        # close any open break first
        await self._close_open_break(rec, now)
        rec.clock_out_at = now
        if latitude is not None:
            rec.out_latitude = latitude
        if longitude is not None:
            rec.out_longitude = longitude
        gross = int((now - _as_utc(rec.clock_in_at)).total_seconds() // 60)
        rec.worked_minutes = max(0, gross - rec.break_minutes)
        shift = await self._active_shift(actor.organization_id, user_id, work_date) if rec.shift_id is None else \
            (await self.db.execute(select(Shift).filter(Shift.id == rec.shift_id))).scalars().first()
        if shift and not shift.is_flexible:
            # Flexible shifts have no fixed end, so early-logout / half-day don't apply.
            _, end_utc = self._bounds(tz, work_date, shift)
            if now < end_utc:
                rec.is_early_logout = True
                rec.early_minutes = int((end_utc - now).total_seconds() // 60)
            # half day if worked less than half the shift span
            shift_minutes = max(1, int((end_utc - self._bounds(tz, work_date, shift)[0]).total_seconds() // 60))
            if rec.worked_minutes < shift_minutes / 2 and rec.status in ("present", "late"):
                rec.status = "half_day"
        self.db.add(rec)
        await self.db.flush()
        await self.db.refresh(rec)
        if rec.is_early_logout:
            await self._notify_manager(actor, user_id, "Early logout",
                                       f"{await self._name(user_id)} clocked out {rec.early_minutes} min early.")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ATTENDANCE_CLOCK_OUT", resource_type="attendance", resource_id=str(rec.id),
                                   action_metadata={"user_id": str(user_id), "worked_minutes": rec.worked_minutes})
        return await self._serialize_record(rec)

    async def _open_break(self, rec: AttendanceRecord) -> AttendanceBreak | None:
        return (await self.db.execute(select(AttendanceBreak).filter(
            AttendanceBreak.attendance_id == rec.id, AttendanceBreak.break_end.is_(None),
            AttendanceBreak.is_deleted == False))).scalars().first()

    async def _close_open_break(self, rec: AttendanceRecord, now: datetime) -> None:
        ob = await self._open_break(rec)
        if ob:
            ob.break_end = now
            ob.minutes = max(0, int((now - _as_utc(ob.break_start)).total_seconds() // 60))
            rec.break_minutes = (rec.break_minutes or 0) + ob.minutes
            self.db.add(ob)
            self.db.add(rec)
            await self.db.flush()

    async def break_start(self, actor: User, reason: str | None = None) -> dict:
        tz = await self._org_tz(actor.organization_id)
        work_date = _now().astimezone(tz).date()
        rec = await self._record_for(actor.organization_id, actor.id, work_date)
        if not rec or not rec.clock_in_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clock in before taking a break.")
        if rec.clock_out_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already clocked out.")
        if await self._open_break(rec):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already on a break.")
        self.db.add(AttendanceBreak(organization_id=actor.organization_id, attendance_id=rec.id,
                                    break_start=_now(), reason=reason))
        await self.db.flush()
        return await self._serialize_record(rec)

    async def break_end(self, actor: User) -> dict:
        tz = await self._org_tz(actor.organization_id)
        work_date = _now().astimezone(tz).date()
        rec = await self._record_for(actor.organization_id, actor.id, work_date)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No attendance record today.")
        if not await self._open_break(rec):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not currently on a break.")
        await self._close_open_break(rec, _now())
        return await self._serialize_record(rec)

    # ================= Biometric ingest =================
    async def biometric_punch(self, actor: User, data: dict) -> dict:
        """Device/mobile punch ingest. A sync account (Manager/OrgAdmin) posts
        punches on behalf of employees; type in|out maps to clock in/out with
        source='biometric'. Integration-ready seam for external devices."""
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Biometric ingest requires a manager/admin sync account.")
        user_id = data.get("user_id")
        if not user_id and data.get("email"):
            user_id = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.email == data["email"],
                User.is_deleted == False))).scalar()
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id or a known email is required.")
        ptype = (data.get("type") or "").lower()
        at = data.get("timestamp")
        kwargs = dict(target_user_id=user_id, source="biometric", device_id=data.get("device_id"),
                      latitude=data.get("latitude"), longitude=data.get("longitude"), at=at)
        if ptype == "in":
            return await self.clock_in(actor, **kwargs)
        if ptype == "out":
            kwargs.pop("source", None)
            kwargs.pop("device_id", None)
            return await self.clock_out(actor, target_user_id=user_id, latitude=data.get("latitude"),
                                        longitude=data.get("longitude"), at=at)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type must be 'in' or 'out'.")

    # ================= Records / history =================
    async def my_today(self, actor: User) -> dict:
        tz = await self._org_tz(actor.organization_id)
        work_date = _now().astimezone(tz).date()
        rec = await self._record_for(actor.organization_id, actor.id, work_date)
        shift = await self._active_shift(actor.organization_id, actor.id, work_date)
        out = {"work_date": work_date.isoformat(), "record": await self._serialize_record(rec) if rec else None,
               "shift": self._serialize_shift(shift) if shift else None,
               "on_break": bool(rec and await self._open_break(rec)) if rec else False}
        return out

    async def list_records(self, actor: User, *, user_id=None, date_from=None, date_to=None,
                           status_filter=None, skip=0, limit=100) -> dict:
        q = select(AttendanceRecord).filter(AttendanceRecord.organization_id == actor.organization_id,
                                            AttendanceRecord.is_deleted == False)
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            q = q.filter(AttendanceRecord.user_id == user_id)
        elif not self._can_admin(actor):
            # non-admins see themselves + (managers) their downline
            if actor.role == "Manager":
                q = q.filter(AttendanceRecord.user_id.in_(list(await self._downline_ids(actor))))
            else:
                q = q.filter(AttendanceRecord.user_id == actor.id)
        if date_from:
            q = q.filter(AttendanceRecord.work_date >= date_from)
        if date_to:
            q = q.filter(AttendanceRecord.work_date <= date_to)
        if status_filter:
            q = q.filter(AttendanceRecord.status == status_filter)
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(AttendanceRecord.work_date.desc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize_record(r) for r in rows], "total": total}

    # ================= Corrections & approvals =================
    async def request_correction(self, actor: User, data: dict) -> dict:
        user_id = data.get("user_id") or actor.id
        if user_id != actor.id and not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot request correction for another user.")
        work_date = data["work_date"]
        rec = await self._record_for(actor.organization_id, user_id, work_date)
        c = AttendanceCorrection(organization_id=actor.organization_id,
                                 attendance_id=rec.id if rec else None, user_id=user_id, work_date=work_date,
                                 reason=data["reason"], proposed=data.get("proposed"), status="pending",
                                 requested_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        # notify the employee's manager (approver)
        approver = await self._manager_of(user_id)
        if approver and approver != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=approver, category="attendance",
                title="Attendance correction to review",
                body=f"{await self._name(user_id)} requested a correction for {work_date}.",
                link_url="/attendance", priority="high", action_metadata={"correction_id": str(c.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ATTENDANCE_CORRECTION_REQUESTED", resource_type="attendance",
                                   resource_id=str(c.id), action_metadata={"work_date": str(work_date)})
        return await self._serialize_correction(c)

    async def list_corrections(self, actor: User, *, status_filter=None, mine=False) -> list[dict]:
        q = select(AttendanceCorrection).filter(
            AttendanceCorrection.organization_id == actor.organization_id,
            AttendanceCorrection.is_deleted == False)
        if mine:
            q = q.filter(AttendanceCorrection.user_id == actor.id)
        elif not self._can_admin(actor):
            if actor.role == "Manager":
                q = q.filter(AttendanceCorrection.user_id.in_(list(await self._downline_ids(actor))))
            else:
                q = q.filter(AttendanceCorrection.user_id == actor.id)
        if status_filter:
            q = q.filter(AttendanceCorrection.status == status_filter)
        rows = list((await self.db.execute(q.order_by(AttendanceCorrection.created_at.desc()))).scalars().all())
        return [await self._serialize_correction(c) for c in rows]

    async def review_correction(self, actor: User, correction_id: uuid.UUID, approve: bool, note: str | None = None) -> dict:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can review corrections.")
        c = (await self.db.execute(select(AttendanceCorrection).filter(
            AttendanceCorrection.id == correction_id, AttendanceCorrection.organization_id == actor.organization_id,
            AttendanceCorrection.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction not found")
        if c.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Correction already reviewed.")
        # a Manager may only review their downline's requests
        if actor.role == "Manager" and c.user_id not in await self._downline_ids(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your team.")
        c.status = "approved" if approve else "rejected"
        c.reviewed_by = actor.id
        c.reviewed_at = _now()
        c.review_note = note
        if approve:
            await self._apply_correction(actor, c)
        self.db.add(c)
        await self.db.flush()
        await self.notifier.create_notification(
            organization_id=actor.organization_id, user_id=c.requested_by, category="attendance",
            title=f"Correction {c.status}", body=f"Your attendance correction for {c.work_date} was {c.status}.",
            link_url="/attendance", action_metadata={"correction_id": str(c.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action=f"ATTENDANCE_CORRECTION_{'APPROVED' if approve else 'REJECTED'}",
                                   resource_type="attendance", resource_id=str(c.id))
        return await self._serialize_correction(c)

    async def _apply_correction(self, actor: User, c: AttendanceCorrection) -> None:
        rec = await self._record_for(actor.organization_id, c.user_id, c.work_date, create=True, created_by=actor.id)
        p = c.proposed or {}
        for field in ("clock_in_at", "clock_out_at"):
            if p.get(field):
                val = p[field]
                if isinstance(val, str):
                    val = datetime.fromisoformat(val.replace("Z", "+00:00"))
                if val.tzinfo is None:
                    val = val.replace(tzinfo=timezone.utc)
                setattr(rec, field, val.astimezone(timezone.utc))
        if p.get("status") in ATT_STATUSES:
            rec.status = p["status"]
        if p.get("notes"):
            rec.notes = p["notes"]
        if rec.clock_in_at and rec.clock_out_at:
            gross = int((_as_utc(rec.clock_out_at) - _as_utc(rec.clock_in_at)).total_seconds() // 60)
            rec.worked_minutes = max(0, gross - (rec.break_minutes or 0))
        c.attendance_id = rec.id
        self.db.add(rec)
        await self.db.flush()

    # ================= Dashboard / reports =================
    async def dashboard(self, actor: User) -> dict:
        tz = await self._org_tz(actor.organization_id)
        work_date = _now().astimezone(tz).date()
        # scope of users
        if self._can_admin(actor):
            scope = None
        elif actor.role == "Manager":
            scope = await self._downline_ids(actor)
        else:
            scope = {actor.id}
        rq = select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == actor.organization_id,
            AttendanceRecord.is_deleted == False, AttendanceRecord.work_date == work_date)
        if scope is not None:
            rq = rq.filter(AttendanceRecord.user_id.in_(list(scope)))
        recs = list((await self.db.execute(rq)).scalars().all())
        present = sum(1 for r in recs if r.clock_in_at)
        late = sum(1 for r in recs if r.is_late)
        clocked_out = sum(1 for r in recs if r.clock_out_at)
        on_break = 0
        for r in recs:
            if r.clock_in_at and not r.clock_out_at and await self._open_break(r):
                on_break += 1
        # headcount (active users in scope)
        uq = select(func.count(User.id)).filter(
            User.organization_id == actor.organization_id, User.is_deleted == False, User.is_active == True)
        if scope is not None:
            uq = uq.filter(User.id.in_(list(scope)))
        headcount = (await self.db.execute(uq)).scalar() or 0
        pending_corr = (await self.db.execute(select(func.count(AttendanceCorrection.id)).filter(
            AttendanceCorrection.organization_id == actor.organization_id,
            AttendanceCorrection.is_deleted == False, AttendanceCorrection.status == "pending",
            *( [AttendanceCorrection.user_id.in_(list(scope))] if scope is not None else [] )))).scalar() or 0
        return {"work_date": work_date.isoformat(), "headcount": headcount, "present": present,
                "absent": max(0, headcount - present), "late": late, "on_break": on_break,
                "clocked_out": clocked_out, "still_working": present - clocked_out,
                "pending_corrections": pending_corr}

    async def monthly_report(self, actor: User, year: int, month: int, user_id=None) -> dict:
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            scope = {user_id}
        elif self._can_admin(actor):
            scope = None
        elif actor.role == "Manager":
            scope = await self._downline_ids(actor)
        else:
            scope = {actor.id}
        first = date(year, month, 1)
        last = date(year, month, _cal.monthrange(year, month)[1])
        q = select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == actor.organization_id, AttendanceRecord.is_deleted == False,
            AttendanceRecord.work_date >= first, AttendanceRecord.work_date <= last)
        if scope is not None:
            q = q.filter(AttendanceRecord.user_id.in_(list(scope)))
        recs = list((await self.db.execute(q)).scalars().all())
        by_user: dict[uuid.UUID, dict] = {}
        for r in recs:
            u = by_user.setdefault(r.user_id, {"present_days": 0, "late_days": 0, "early_days": 0,
                                               "half_days": 0, "leave_days": 0, "worked_minutes": 0,
                                               "break_minutes": 0})
            if r.clock_in_at:
                u["present_days"] += 1
            if r.is_late:
                u["late_days"] += 1
            if r.is_early_logout:
                u["early_days"] += 1
            if r.status == "half_day":
                u["half_days"] += 1
            if r.status == "on_leave":
                u["leave_days"] += 1
            u["worked_minutes"] += r.worked_minutes or 0
            u["break_minutes"] += r.break_minutes or 0
        names = await self._names(set(by_user.keys()))
        rows = []
        for uid, u in by_user.items():
            rows.append({"user_id": str(uid), "name": names.get(uid, ""),
                         "worked_hours": round(u["worked_minutes"] / 60, 1),
                         "break_hours": round(u["break_minutes"] / 60, 1), **u})
        rows.sort(key=lambda x: -x["present_days"])
        return {"year": year, "month": month, "working_days_in_month": last.day, "rows": rows}

    # ---------- notification/name helpers ----------
    async def _manager_of(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return (await self.db.execute(select(User.reporting_to_id).filter(User.id == user_id))).scalar()

    async def _notify_manager(self, actor: User, user_id: uuid.UUID, title: str, body: str) -> None:
        mgr = await self._manager_of(user_id)
        if mgr and mgr != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=mgr, category="attendance",
                title=title, body=body, link_url="/attendance", action_metadata={"user_id": str(user_id)})

    async def _name(self, user_id: uuid.UUID) -> str:
        return (await self._names({user_id})).get(user_id, "A teammate")

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _shift_names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(Shift.id, Shift.name).filter(Shift.id.in_(ids)))
        return {sid: name for sid, name in res.all()}

    # ---------- serializers ----------
    @staticmethod
    def _serialize_shift(s: Shift | None) -> dict | None:
        if not s:
            return None
        return {"id": str(s.id), "name": s.name, "code": s.code,
                "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
                "break_minutes": s.break_minutes, "grace_minutes": s.grace_minutes,
                "working_days": s.working_days or DEFAULT_WORKING_DAYS, "is_night_shift": s.is_night_shift,
                "status": s.status, "color": s.color, "created_at": s.created_at}

    async def _serialize_record(self, r: AttendanceRecord | None) -> dict | None:
        if not r:
            return None
        name = (await self._names({r.user_id})).get(r.user_id)
        return {"id": str(r.id), "user_id": str(r.user_id), "user_name": name,
                "work_date": r.work_date.isoformat(), "shift_id": str(r.shift_id) if r.shift_id else None,
                "clock_in_at": r.clock_in_at.isoformat() if r.clock_in_at else None,
                "clock_out_at": r.clock_out_at.isoformat() if r.clock_out_at else None,
                "status": r.status, "is_late": r.is_late, "late_minutes": r.late_minutes,
                "is_early_logout": r.is_early_logout, "early_minutes": r.early_minutes,
                "worked_minutes": r.worked_minutes, "break_minutes": r.break_minutes,
                "in_latitude": float(r.in_latitude) if r.in_latitude is not None else None,
                "in_longitude": float(r.in_longitude) if r.in_longitude is not None else None,
                "source": r.source, "notes": r.notes}

    async def _serialize_correction(self, c: AttendanceCorrection) -> dict:
        names = await self._names({c.user_id, c.requested_by, c.reviewed_by})
        return {"id": str(c.id), "attendance_id": str(c.attendance_id) if c.attendance_id else None,
                "user_id": str(c.user_id), "user_name": names.get(c.user_id),
                "work_date": c.work_date.isoformat(), "reason": c.reason, "proposed": c.proposed,
                "status": c.status, "requested_by": str(c.requested_by),
                "requested_by_name": names.get(c.requested_by),
                "reviewed_by_name": names.get(c.reviewed_by) if c.reviewed_by else None,
                "review_note": c.review_note, "created_at": c.created_at}

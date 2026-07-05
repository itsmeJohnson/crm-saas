"""Shift Management service.

Owns the richer shift surface on top of the `shifts` table introduced by the
Attendance module (which keeps its own simpler /attendance/shifts CRUD working):
shift types (morning/evening/night/flexible/general), flexible shifts, preset
creation, and — the genuinely new pieces — shift rotations, a per-day shift
calendar (resolving direct assignments, rotations, weekly-offs and holidays),
shift-scoped attendance, and shift reports.

`resolve_shift_for_user` is the single authority for "which shift applies to a
user on a date": a direct ShiftAssignment wins; otherwise an active rotation is
cycled from the member's anchor date. AttendanceService delegates to it, so
clock-in/out honour rotations too.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.calendar_event import Holiday
from app.models.attendance import Shift, ShiftAssignment, AttendanceRecord
from app.models.shift_rotation import ShiftRotation, ShiftRotationMember
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_WORKING_DAYS = ["mon", "tue", "wed", "thu", "fri"]
SHIFT_TYPES = ("morning", "evening", "night", "flexible", "general")
# name, code, start, end, type, flexible, night
PRESETS = [
    ("Morning Shift", "MORN", "06:00", "14:00", "morning", False, False),
    ("Evening Shift", "EVE", "14:00", "22:00", "evening", False, False),
    ("Night Shift", "NIGHT", "22:00", "06:00", "night", False, True),
    ("Flexible Shift", "FLEX", "09:00", "18:00", "flexible", True, False),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(v) -> time:
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        p = v.split(":")
        return time(int(p[0]), int(p[1]) if len(p) > 1 else 0)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time value.")


class ShiftService:
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can manage shifts.")

    async def _downline_ids(self, actor: User) -> set[uuid.UUID]:
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return set(ids) | {actor.id}

    async def _scope_user_ids(self, actor: User) -> set[uuid.UUID] | None:
        if self._can_admin(actor):
            return None
        if actor.role == "Manager":
            return await self._downline_ids(actor)
        return {actor.id}

    # ================= Shifts =================
    async def _get(self, actor: User, shift_id: uuid.UUID) -> Shift:
        s = (await self.db.execute(select(Shift).filter(
            Shift.id == shift_id, Shift.organization_id == actor.organization_id,
            Shift.is_deleted == False))).scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
        return s

    async def _validate_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(Shift.id).filter(Shift.organization_id == actor.organization_id,
                                    Shift.code == code, Shift.is_deleted == False)
        if exclude_id:
            q = q.filter(Shift.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Shift code '{code}' already exists.")

    async def create_shift(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        shift_type = data.get("shift_type", "general")
        if shift_type not in SHIFT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"shift_type must be one of {list(SHIFT_TYPES)}")
        await self._validate_code(actor, data.get("code"))
        wd = data.get("working_days")
        if wd:
            bad = [d for d in wd if d not in WEEKDAYS]
            if bad:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid working_days: {bad}")
        start_t = _parse_time(data["start_time"])
        end_t = _parse_time(data["end_time"])
        # None (field omitted) → derive from the shift type; explicit bool wins.
        is_flexible = data.get("is_flexible")
        is_flexible = (shift_type == "flexible") if is_flexible is None else bool(is_flexible)
        is_night = data.get("is_night_shift")
        is_night = (shift_type == "night" or end_t <= start_t) if is_night is None else bool(is_night)
        s = Shift(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                  start_time=start_t, end_time=end_t, break_minutes=int(data.get("break_minutes", 0)),
                  grace_minutes=int(data.get("grace_minutes", 0)), working_days=wd,
                  is_night_shift=is_night,
                  shift_type=shift_type, is_flexible=is_flexible,
                  works_on_holidays=bool(data.get("works_on_holidays", False)),
                  status=data.get("status", "active"), color=data.get("color"), created_by=actor.id)
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SHIFT_CREATED", resource_type="shift", resource_id=str(s.id),
                                   action_metadata={"name": s.name, "type": shift_type})
        return self._serialize(s)

    async def create_presets(self, actor: User) -> dict:
        """Create the standard Morning/Evening/Night/Flexible shifts (skips any
        whose code already exists). Covers the common shift set in one click."""
        self._require_admin(actor)
        created = 0
        for name, code, start, end, stype, flex, night in PRESETS:
            exists = (await self.db.execute(select(Shift.id).filter(
                Shift.organization_id == actor.organization_id, Shift.code == code,
                Shift.is_deleted == False))).scalar()
            if exists:
                continue
            self.db.add(Shift(organization_id=actor.organization_id, name=name, code=code,
                              start_time=_parse_time(start), end_time=_parse_time(end), break_minutes=60,
                              grace_minutes=10, is_night_shift=night, shift_type=stype, is_flexible=flex,
                              status="active", created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"created": created}

    async def update_shift(self, actor: User, shift_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        s = await self._get(actor, shift_id)
        if "shift_type" in data and data["shift_type"] not in SHIFT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"shift_type must be one of {list(SHIFT_TYPES)}")
        if "code" in data:
            await self._validate_code(actor, data.get("code"), exclude_id=s.id)
        for k in ("name", "code", "break_minutes", "grace_minutes", "working_days", "is_night_shift",
                  "shift_type", "is_flexible", "works_on_holidays", "status", "color"):
            if k in data:
                setattr(s, k, data[k])
        if "start_time" in data:
            s.start_time = _parse_time(data["start_time"])
        if "end_time" in data:
            s.end_time = _parse_time(data["end_time"])
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return self._serialize(s)

    async def delete_shift(self, actor: User, shift_id: uuid.UUID) -> None:
        self._require_admin(actor)
        s = await self._get(actor, shift_id)
        active = (await self.db.execute(select(func.count(ShiftAssignment.id)).filter(
            ShiftAssignment.shift_id == s.id, ShiftAssignment.is_deleted == False,
            or_(ShiftAssignment.end_date.is_(None), ShiftAssignment.end_date >= date.today())))).scalar() or 0
        if active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{active} active assignment(s) use this shift. Reassign them first.")
        # a shift referenced by a rotation sequence can't be deleted either
        rots = list((await self.db.execute(select(ShiftRotation).filter(
            ShiftRotation.organization_id == actor.organization_id, ShiftRotation.is_deleted == False))).scalars().all())
        if any(str(s.id) in (r.shift_sequence or []) for r in rots):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This shift is used by a rotation. Remove it from the rotation first.")
        s.is_deleted = True
        self.db.add(s)
        await self.db.flush()

    async def list_shifts(self, actor: User, status_filter=None, shift_type=None) -> list[dict]:
        q = select(Shift).filter(Shift.organization_id == actor.organization_id, Shift.is_deleted == False)
        if status_filter:
            q = q.filter(Shift.status == status_filter)
        if shift_type:
            q = q.filter(Shift.shift_type == shift_type)
        rows = list((await self.db.execute(q.order_by(Shift.start_time.asc()))).scalars().all())
        return [self._serialize(s) for s in rows]

    # ================= Direct assignment =================
    async def assign_shift(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        shift = await self._get(actor, data["shift_id"])
        start_date = data.get("start_date") or date.today()
        end_date = data.get("end_date")
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(data["user_ids"]), User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().all())
        for u in users:
            open_rows = list((await self.db.execute(select(ShiftAssignment).filter(
                ShiftAssignment.user_id == u.id, ShiftAssignment.organization_id == actor.organization_id,
                ShiftAssignment.is_deleted == False, ShiftAssignment.end_date.is_(None)))).scalars().all())
            for r in open_rows:
                if r.start_date < start_date:
                    r.end_date = start_date - timedelta(days=1)
                else:
                    r.is_deleted = True
                self.db.add(r)
            self.db.add(ShiftAssignment(organization_id=actor.organization_id, user_id=u.id, shift_id=shift.id,
                                        start_date=start_date, end_date=end_date, created_by=actor.id))
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=u.id, category="shift",
                title="Shift assigned", body=f"You were assigned to the {shift.name} shift.",
                link_url="/shifts", action_metadata={"shift_id": str(shift.id)})
        await self.db.flush()
        # workflow: shift assigned (per user)
        from app.services.workflow_service import WorkflowService
        wf = WorkflowService(self.db)
        for u in users:
            ent = _ShiftEvent(actor.organization_id, u.id, shift.id)
            await wf.run("shift_assigned", ent, actor, entity_type="shift")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SHIFT_ASSIGNED", resource_type="shift", resource_id=str(shift.id),
                                   action_metadata={"users": len(users)})
        return {"assigned": len(users)}

    # ================= Rotations =================
    async def _get_rotation(self, actor: User, rotation_id: uuid.UUID) -> ShiftRotation:
        r = (await self.db.execute(select(ShiftRotation).filter(
            ShiftRotation.id == rotation_id, ShiftRotation.organization_id == actor.organization_id,
            ShiftRotation.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rotation not found")
        return r

    async def _validate_sequence(self, actor: User, seq: list) -> list[str]:
        if not seq or len(seq) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A rotation needs at least two shifts.")
        ids = []
        for sid in seq:
            s = (await self.db.execute(select(Shift.id).filter(
                Shift.id == uuid.UUID(str(sid)), Shift.organization_id == actor.organization_id,
                Shift.is_deleted == False))).scalar()
            if not s:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Shift {sid} not found.")
            ids.append(str(sid))
        return ids

    async def create_rotation(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        if data.get("code"):
            dup = (await self.db.execute(select(ShiftRotation.id).filter(
                ShiftRotation.organization_id == actor.organization_id, ShiftRotation.code == data["code"],
                ShiftRotation.is_deleted == False))).scalar()
            if dup:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Rotation code '{data['code']}' already exists.")
        seq = await self._validate_sequence(actor, data["shift_sequence"])
        rotation_days = int(data.get("rotation_days", 7))
        if rotation_days < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rotation_days must be at least 1.")
        r = ShiftRotation(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                          description=data.get("description"), shift_sequence=seq, rotation_days=rotation_days,
                          status=data.get("status", "active"), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SHIFT_ROTATION_CREATED", resource_type="shift", resource_id=str(r.id),
                                   action_metadata={"name": r.name})
        return await self._serialize_rotation(r)

    async def update_rotation(self, actor: User, rotation_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        r = await self._get_rotation(actor, rotation_id)
        if "shift_sequence" in data:
            r.shift_sequence = await self._validate_sequence(actor, data["shift_sequence"])
        if "rotation_days" in data and data["rotation_days"] is not None:
            if int(data["rotation_days"]) < 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rotation_days must be at least 1.")
            r.rotation_days = int(data["rotation_days"])
        for k in ("name", "code", "description", "status"):
            if k in data:
                setattr(r, k, data[k])
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        return await self._serialize_rotation(r)

    async def delete_rotation(self, actor: User, rotation_id: uuid.UUID) -> None:
        self._require_admin(actor)
        r = await self._get_rotation(actor, rotation_id)
        r.is_deleted = True
        self.db.add(r)
        # soft-delete memberships
        for m in list((await self.db.execute(select(ShiftRotationMember).filter(
                ShiftRotationMember.rotation_id == r.id, ShiftRotationMember.is_deleted == False))).scalars().all()):
            m.is_deleted = True
            self.db.add(m)
        await self.db.flush()

    async def list_rotations(self, actor: User, status_filter=None) -> list[dict]:
        q = select(ShiftRotation).filter(ShiftRotation.organization_id == actor.organization_id,
                                         ShiftRotation.is_deleted == False)
        if status_filter:
            q = q.filter(ShiftRotation.status == status_filter)
        rows = list((await self.db.execute(q.order_by(ShiftRotation.name.asc()))).scalars().all())
        return [await self._serialize_rotation(r) for r in rows]

    async def assign_rotation(self, actor: User, rotation_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        r = await self._get_rotation(actor, rotation_id)
        anchor = data.get("anchor_date") or date.today()
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(data["user_ids"]), User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().all())
        for u in users:
            prev = (await self.db.execute(select(ShiftRotationMember).filter(
                ShiftRotationMember.rotation_id == r.id, ShiftRotationMember.user_id == u.id))).scalars().first()
            if prev:
                prev.is_deleted = False
                prev.anchor_date = anchor
                prev.end_date = data.get("end_date")
                self.db.add(prev)
            else:
                self.db.add(ShiftRotationMember(organization_id=actor.organization_id, rotation_id=r.id,
                                                user_id=u.id, anchor_date=anchor, end_date=data.get("end_date"),
                                                created_by=actor.id))
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=u.id, category="shift",
                title="Shift rotation assigned", body=f"You were added to the {r.name} rotation.",
                link_url="/shifts", action_metadata={"rotation_id": str(r.id)})
        await self.db.flush()
        from app.services.workflow_service import WorkflowService
        wf = WorkflowService(self.db)
        for u in users:
            cur = await self._rotation_shift_for(actor.organization_id, r, u.id, date.today())
            ent = _ShiftEvent(actor.organization_id, u.id, cur.id if cur else None)
            await wf.run("shift_assigned", ent, actor, entity_type="shift")
        return {"assigned": len(users)}

    async def rotation_members(self, actor: User, rotation_id: uuid.UUID) -> list[dict]:
        await self._get_rotation(actor, rotation_id)
        rows = list((await self.db.execute(select(ShiftRotationMember).filter(
            ShiftRotationMember.rotation_id == rotation_id, ShiftRotationMember.is_deleted == False))).scalars().all())
        names = await self._names({m.user_id for m in rows})
        return [{"id": str(m.id), "user_id": str(m.user_id), "user_name": names.get(m.user_id),
                 "anchor_date": m.anchor_date.isoformat(), "end_date": m.end_date.isoformat() if m.end_date else None}
                for m in rows]

    async def remove_rotation_member(self, actor: User, rotation_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        self._require_admin(actor)
        m = (await self.db.execute(select(ShiftRotationMember).filter(
            ShiftRotationMember.rotation_id == rotation_id, ShiftRotationMember.user_id == user_id,
            ShiftRotationMember.is_deleted == False))).scalars().first()
        if not m:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
        m.is_deleted = True
        self.db.add(m)
        await self.db.flush()
        return {"removed": 1}

    # ================= Resolution =================
    async def _rotation_shift_for(self, org_id, rotation: ShiftRotation, user_id: uuid.UUID, on: date) -> Shift | None:
        m = (await self.db.execute(select(ShiftRotationMember).filter(
            ShiftRotationMember.rotation_id == rotation.id, ShiftRotationMember.user_id == user_id,
            ShiftRotationMember.is_deleted == False))).scalars().first()
        if not m or on < m.anchor_date or (m.end_date and on > m.end_date):
            return None
        seq = rotation.shift_sequence or []
        if not seq:
            return None
        offset = (on - m.anchor_date).days
        idx = (offset // max(1, rotation.rotation_days)) % len(seq)
        try:
            sid = uuid.UUID(str(seq[idx]))
        except (ValueError, IndexError):
            return None
        return (await self.db.execute(select(Shift).filter(
            Shift.id == sid, Shift.organization_id == org_id, Shift.is_deleted == False))).scalars().first()

    async def resolve_shift_for_user(self, org_id: uuid.UUID, user_id: uuid.UUID, on: date) -> Shift | None:
        """Direct assignment wins; otherwise cycle any active rotation. This is
        the single source of truth used by both the shift calendar and
        AttendanceService (so clock-in/out honour rotations)."""
        row = (await self.db.execute(select(ShiftAssignment).filter(
            ShiftAssignment.organization_id == org_id, ShiftAssignment.user_id == user_id,
            ShiftAssignment.is_deleted == False, ShiftAssignment.start_date <= on,
            or_(ShiftAssignment.end_date.is_(None), ShiftAssignment.end_date >= on))
            .order_by(ShiftAssignment.start_date.desc()))).scalars().first()
        if row:
            s = (await self.db.execute(select(Shift).filter(
                Shift.id == row.shift_id, Shift.is_deleted == False))).scalars().first()
            if s:
                return s
        rotations = list((await self.db.execute(select(ShiftRotation).filter(
            ShiftRotation.organization_id == org_id, ShiftRotation.is_deleted == False,
            ShiftRotation.status == "active"))).scalars().all())
        for r in rotations:
            s = await self._rotation_shift_for(org_id, r, user_id, on)
            if s:
                return s
        return None

    # ================= Shift calendar =================
    async def calendar(self, actor: User, date_from: date, date_to: date, user_id=None) -> list[dict]:
        """Per-user, per-day shift schedule over a range: the resolved shift, or
        'weekly_off' (day not in the shift's working days) or 'holiday'."""
        if (date_to - date_from).days > 45:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Range cannot exceed 45 days.")
        if user_id:
            if user_id != actor.id and not self._is_manager(actor):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view this user.")
            user_ids = [user_id]
        else:
            scope = await self._scope_user_ids(actor)
            uq = select(User.id).filter(User.organization_id == actor.organization_id,
                                        User.is_deleted == False, User.is_active == True)
            if scope is not None:
                uq = uq.filter(User.id.in_(list(scope)))
            user_ids = list((await self.db.execute(uq)).scalars().all())
        names = await self._names(set(user_ids))
        holidays = await self._holidays_in(actor.organization_id, date_from, date_to)
        out = []
        for uid in user_ids:
            cur = date_from
            while cur <= date_to:
                shift = await self.resolve_shift_for_user(actor.organization_id, uid, cur)
                entry = {"user_id": str(uid), "user_name": names.get(uid), "date": cur.isoformat(),
                         "shift_id": None, "shift_name": None, "shift_type": None,
                         "start_time": None, "end_time": None, "state": "off"}
                if shift:
                    wd = shift.working_days or DEFAULT_WORKING_DAYS
                    is_working_day = WEEKDAYS[cur.weekday()] in wd
                    if cur in holidays and not shift.works_on_holidays:
                        entry["state"] = "holiday"
                    elif not is_working_day:
                        entry["state"] = "weekly_off"
                    else:
                        entry.update({"shift_id": str(shift.id), "shift_name": shift.name,
                                      "shift_type": shift.shift_type,
                                      "start_time": shift.start_time.strftime("%H:%M"),
                                      "end_time": shift.end_time.strftime("%H:%M"), "state": "working"})
                elif cur in holidays:
                    entry["state"] = "holiday"
                if entry["state"] != "off":
                    out.append(entry)
                cur += timedelta(days=1)
        return out

    # ================= Shift attendance & reports =================
    async def shift_attendance(self, actor: User, shift_id: uuid.UUID, date_from: date, date_to: date) -> dict:
        shift = await self._get(actor, shift_id)
        q = select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == actor.organization_id, AttendanceRecord.is_deleted == False,
            AttendanceRecord.shift_id == shift_id, AttendanceRecord.work_date >= date_from,
            AttendanceRecord.work_date <= date_to)
        scope = await self._scope_user_ids(actor)
        if scope is not None:
            q = q.filter(AttendanceRecord.user_id.in_(list(scope)))
        recs = list((await self.db.execute(q.order_by(AttendanceRecord.work_date.desc()))).scalars().all())
        names = await self._names({r.user_id for r in recs})
        return {"shift_id": str(shift.id), "shift_name": shift.name,
                "records": [{"user_id": str(r.user_id), "user_name": names.get(r.user_id),
                             "work_date": r.work_date.isoformat(), "status": r.status,
                             "is_late": r.is_late, "late_minutes": r.late_minutes,
                             "is_early_logout": r.is_early_logout, "worked_minutes": r.worked_minutes}
                            for r in recs]}

    async def reports(self, actor: User, date_from: date, date_to: date) -> list[dict]:
        """Per-shift attendance rollup for a period."""
        shifts = list((await self.db.execute(select(Shift).filter(
            Shift.organization_id == actor.organization_id, Shift.is_deleted == False,
            Shift.status == "active"))).scalars().all())
        scope = await self._scope_user_ids(actor)
        out = []
        for s in shifts:
            q = select(AttendanceRecord).filter(
                AttendanceRecord.organization_id == actor.organization_id, AttendanceRecord.is_deleted == False,
                AttendanceRecord.shift_id == s.id, AttendanceRecord.work_date >= date_from,
                AttendanceRecord.work_date <= date_to)
            if scope is not None:
                q = q.filter(AttendanceRecord.user_id.in_(list(scope)))
            recs = list((await self.db.execute(q)).scalars().all())
            # current headcount assigned (direct assignments only, cheap)
            assigned = (await self.db.execute(select(func.count(func.distinct(ShiftAssignment.user_id))).filter(
                ShiftAssignment.shift_id == s.id, ShiftAssignment.is_deleted == False,
                or_(ShiftAssignment.end_date.is_(None), ShiftAssignment.end_date >= date.today())))).scalar() or 0
            present = sum(1 for r in recs if r.clock_in_at)
            out.append({"shift_id": str(s.id), "shift_name": s.name, "shift_type": s.shift_type,
                        "assigned": assigned, "records": len(recs), "present": present,
                        "late": sum(1 for r in recs if r.is_late),
                        "early_logout": sum(1 for r in recs if r.is_early_logout),
                        "on_leave": sum(1 for r in recs if r.status == "on_leave"),
                        "worked_hours": round(sum(r.worked_minutes or 0 for r in recs) / 60, 1)})
        out.sort(key=lambda x: -x["records"])
        return out

    async def dashboard(self, actor: User) -> dict:
        today = date.today()
        shifts = list((await self.db.execute(select(Shift).filter(
            Shift.organization_id == actor.organization_id, Shift.is_deleted == False))).scalars().all())
        active = [s for s in shifts if s.status == "active"]
        rotations = (await self.db.execute(select(func.count(ShiftRotation.id)).filter(
            ShiftRotation.organization_id == actor.organization_id, ShiftRotation.is_deleted == False,
            ShiftRotation.status == "active"))).scalar() or 0
        # my shift today
        my = await self.resolve_shift_for_user(actor.organization_id, actor.id, today)
        by_type: dict[str, int] = {}
        for s in active:
            by_type[s.shift_type] = by_type.get(s.shift_type, 0) + 1
        return {"total_shifts": len(active), "flexible_shifts": sum(1 for s in active if s.is_flexible),
                "night_shifts": sum(1 for s in active if s.shift_type == "night"),
                "active_rotations": rotations, "by_type": by_type,
                "my_shift_today": self._serialize(my) if my else None}

    # ---------- helpers ----------
    async def _holidays_in(self, org_id, start: date, end: date) -> set[date]:
        rows = list((await self.db.execute(select(Holiday).filter(
            Holiday.organization_id == org_id, Holiday.is_deleted == False))).scalars().all())
        out: set[date] = set()
        for h in rows:
            if h.recurring_annual:
                for yr in range(start.year, end.year + 1):
                    try:
                        d = h.holiday_date.replace(year=yr)
                    except ValueError:
                        continue
                    if start <= d <= end:
                        out.add(d)
            elif start <= h.holiday_date <= end:
                out.add(h.holiday_date)
        return out

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    def _serialize(self, s: Shift | None) -> dict | None:
        if not s:
            return None
        return {"id": str(s.id), "name": s.name, "code": s.code, "shift_type": s.shift_type,
                "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
                "break_minutes": s.break_minutes, "grace_minutes": s.grace_minutes,
                "working_days": s.working_days or DEFAULT_WORKING_DAYS, "is_night_shift": s.is_night_shift,
                "is_flexible": s.is_flexible, "works_on_holidays": s.works_on_holidays,
                "status": s.status, "color": s.color, "created_at": s.created_at}

    async def _serialize_rotation(self, r: ShiftRotation) -> dict:
        snames = await self._shift_names_ordered(r.shift_sequence or [])
        member_count = (await self.db.execute(select(func.count(ShiftRotationMember.id)).filter(
            ShiftRotationMember.rotation_id == r.id, ShiftRotationMember.is_deleted == False))).scalar() or 0
        return {"id": str(r.id), "name": r.name, "code": r.code, "description": r.description,
                "shift_sequence": [str(x) for x in (r.shift_sequence or [])], "shift_names": snames,
                "rotation_days": r.rotation_days, "status": r.status, "member_count": member_count,
                "created_at": r.created_at}

    async def _shift_names_ordered(self, seq: list) -> list[str]:
        if not seq:
            return []
        ids = [uuid.UUID(str(x)) for x in seq]
        rows = dict((sid, name) for sid, name in (await self.db.execute(
            select(Shift.id, Shift.name).filter(Shift.id.in_(ids)))).all())
        return [rows.get(i, "?") for i in ids]


class _ShiftEvent:
    """Lightweight entity passed to the workflow engine for shift_assigned rules
    (the engine only needs organization_id, id and the condition fields)."""
    def __init__(self, organization_id, user_id, shift_id):
        self.organization_id = organization_id
        self.user_id = user_id
        self.shift_id = shift_id
        self.id = user_id  # audit/resource id

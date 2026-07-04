"""Leave Management service.

Leave types, yearly balances (allocation stored; used/pending derived), and the
apply → approve/reject/cancel lifecycle for both leave and work-from-home
requests. Working-day counting excludes weekends and holidays (the latter read
from the existing `holidays` table — the Holiday Calendar is reused, not
rebuilt). Approving a leave request marks the covered days `on_leave` on the
attendance records, and notifications flow to the approver and requester.
"""
from __future__ import annotations
import calendar as _cal
import uuid
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.calendar_event import Holiday
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveType, LeaveBalance, LeaveRequest
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

OPEN_STATUSES = ("pending", "approved")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


class LeaveService:
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
                                detail="Only an OrgAdmin can manage leave types and allocations.")

    async def _downline_ids(self, actor: User) -> set[uuid.UUID]:
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return set(ids) | {actor.id}

    async def _assert_can_view_user(self, actor: User, user_id: uuid.UUID):
        if actor.id == user_id or self._can_admin(actor):
            return
        if actor.role == "Manager" and user_id in await self._downline_ids(actor):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view this user's leave.")

    async def _manager_of(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return (await self.db.execute(select(User.reporting_to_id).filter(User.id == user_id))).scalar()

    # ================= Leave types =================
    async def _get_type(self, actor: User, type_id: uuid.UUID) -> LeaveType:
        t = (await self.db.execute(select(LeaveType).filter(
            LeaveType.id == type_id, LeaveType.organization_id == actor.organization_id,
            LeaveType.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave type not found")
        return t

    async def _validate_type_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(LeaveType.id).filter(LeaveType.organization_id == actor.organization_id,
                                        LeaveType.code == code, LeaveType.is_deleted == False)
        if exclude_id:
            q = q.filter(LeaveType.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Leave type code '{code}' already exists.")

    async def create_type(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        await self._validate_type_code(actor, data.get("code"))
        t = LeaveType(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                      description=data.get("description"), is_paid=bool(data.get("is_paid", True)),
                      annual_quota=_d(data.get("annual_quota", 0)),
                      max_consecutive_days=data.get("max_consecutive_days"),
                      allow_half_day=bool(data.get("allow_half_day", True)),
                      requires_approval=bool(data.get("requires_approval", True)),
                      deducts_balance=bool(data.get("deducts_balance", True)),
                      color=data.get("color"), status=data.get("status", "active"), created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="LEAVE_TYPE_CREATED", resource_type="leave", resource_id=str(t.id),
                                   action_metadata={"name": t.name})
        return self._serialize_type(t)

    async def update_type(self, actor: User, type_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        t = await self._get_type(actor, type_id)
        if "code" in data:
            await self._validate_type_code(actor, data.get("code"), exclude_id=t.id)
        for k in ("name", "code", "description", "is_paid", "max_consecutive_days", "allow_half_day",
                  "requires_approval", "deducts_balance", "color", "status"):
            if k in data:
                setattr(t, k, data[k])
        if "annual_quota" in data:
            t.annual_quota = _d(data["annual_quota"])
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return self._serialize_type(t)

    async def delete_type(self, actor: User, type_id: uuid.UUID) -> None:
        self._require_admin(actor)
        t = await self._get_type(actor, type_id)
        used = (await self.db.execute(select(func.count(LeaveRequest.id)).filter(
            LeaveRequest.leave_type_id == t.id, LeaveRequest.is_deleted == False,
            LeaveRequest.status.in_(OPEN_STATUSES)))).scalar() or 0
        if used:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{used} open request(s) use this type. Archive it instead.")
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    async def list_types(self, actor: User, status_filter=None) -> list[dict]:
        q = select(LeaveType).filter(LeaveType.organization_id == actor.organization_id,
                                     LeaveType.is_deleted == False)
        if status_filter:
            q = q.filter(LeaveType.status == status_filter)
        rows = list((await self.db.execute(q.order_by(LeaveType.name.asc()))).scalars().all())
        return [self._serialize_type(t) for t in rows]

    # ================= Balances =================
    async def set_allocation(self, actor: User, data: dict) -> dict:
        """Allocate (or update) a user's yearly quota for a leave type."""
        self._require_admin(actor)
        t = await self._get_type(actor, data["leave_type_id"])
        user_id = data["user_id"]
        u = (await self.db.execute(select(User.id).filter(
            User.id == user_id, User.organization_id == actor.organization_id, User.is_deleted == False))).scalar()
        if not u:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found in this org.")
        year = data.get("year") or date.today().year
        bal = (await self.db.execute(select(LeaveBalance).filter(
            LeaveBalance.organization_id == actor.organization_id, LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == t.id, LeaveBalance.year == year,
            LeaveBalance.is_deleted == False))).scalars().first()
        if bal:
            bal.allocated = _d(data.get("allocated", bal.allocated))
            if "carried_forward" in data:
                bal.carried_forward = _d(data["carried_forward"])
        else:
            bal = LeaveBalance(organization_id=actor.organization_id, user_id=user_id, leave_type_id=t.id,
                               year=year, allocated=_d(data.get("allocated", t.annual_quota)),
                               carried_forward=_d(data.get("carried_forward", 0)), created_by=actor.id)
        self.db.add(bal)
        await self.db.flush()
        return await self._balance_row(actor, bal)

    async def _used_pending(self, org_id, user_id, leave_type_id, year) -> tuple[Decimal, Decimal]:
        """Sum approved (used) and pending day_counts for a user/type/year."""
        start, end = date(year, 1, 1), date(year, 12, 31)
        rows = (await self.db.execute(select(LeaveRequest.status, func.coalesce(func.sum(LeaveRequest.day_count), 0)).filter(
            LeaveRequest.organization_id == org_id, LeaveRequest.user_id == user_id,
            LeaveRequest.leave_type_id == leave_type_id, LeaveRequest.is_deleted == False,
            LeaveRequest.request_type == "leave", LeaveRequest.status.in_(OPEN_STATUSES),
            LeaveRequest.start_date >= start, LeaveRequest.start_date <= end)
            .group_by(LeaveRequest.status))).all()
        used = pending = Decimal(0)
        for st, total in rows:
            if st == "approved":
                used = _d(total)
            elif st == "pending":
                pending = _d(total)
        return used, pending

    async def balances(self, actor: User, user_id: uuid.UUID, year: int | None = None) -> list[dict]:
        await self._assert_can_view_user(actor, user_id)
        year = year or date.today().year
        types = list((await self.db.execute(select(LeaveType).filter(
            LeaveType.organization_id == actor.organization_id, LeaveType.is_deleted == False,
            LeaveType.status == "active"))).scalars().all())
        existing = {b.leave_type_id: b for b in (await self.db.execute(select(LeaveBalance).filter(
            LeaveBalance.organization_id == actor.organization_id, LeaveBalance.user_id == user_id,
            LeaveBalance.year == year, LeaveBalance.is_deleted == False))).scalars().all()}
        out = []
        for t in types:
            if not t.deducts_balance:
                continue
            bal = existing.get(t.id)
            allocated = _d(bal.allocated) if bal else _d(t.annual_quota)
            carried = _d(bal.carried_forward) if bal else Decimal(0)
            used, pending = await self._used_pending(actor.organization_id, user_id, t.id, year)
            out.append({"leave_type_id": str(t.id), "leave_type_name": t.name, "color": t.color,
                        "year": year, "allocated": float(allocated), "carried_forward": float(carried),
                        "used": float(used), "pending": float(pending),
                        "available": float(allocated + carried - used - pending)})
        return out

    async def _balance_row(self, actor: User, bal: LeaveBalance) -> dict:
        t = await self._get_type(actor, bal.leave_type_id)
        used, pending = await self._used_pending(actor.organization_id, bal.user_id, bal.leave_type_id, bal.year)
        allocated, carried = _d(bal.allocated), _d(bal.carried_forward)
        return {"leave_type_id": str(bal.leave_type_id), "leave_type_name": t.name, "color": t.color,
                "year": bal.year, "allocated": float(allocated), "carried_forward": float(carried),
                "used": float(used), "pending": float(pending),
                "available": float(allocated + carried - used - pending)}

    # ================= Working-day counting =================
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

    async def _count_days(self, org_id, start: date, end: date, is_half_day: bool) -> Decimal:
        if end < start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date is before start_date.")
        if is_half_day:
            if start != end:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A half day must be a single date.")
            if start.weekday() >= 5:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Half day cannot fall on a weekend.")
            return Decimal("0.5")
        holidays = await self._holidays_in(org_id, start, end)
        days = Decimal(0)
        cur = start
        while cur <= end:
            if cur.weekday() < 5 and cur not in holidays:
                days += 1
            cur += timedelta(days=1)
        return days

    # ================= Apply / lifecycle =================
    async def apply(self, actor: User, data: dict) -> dict:
        user_id = data.get("user_id") or actor.id
        if user_id != actor.id and not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot apply on behalf of another user.")
        request_type = data.get("request_type", "leave")
        if request_type not in ("leave", "wfh"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="request_type must be leave or wfh.")
        start = data["start_date"]
        end = data["end_date"]
        is_half = bool(data.get("is_half_day", False))
        leave_type = None
        if request_type == "leave":
            if not data.get("leave_type_id"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="leave_type_id is required for leave.")
            leave_type = await self._get_type(actor, data["leave_type_id"])
            if leave_type.status != "active":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave type is archived.")
            if is_half and not leave_type.allow_half_day:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This leave type does not allow half days.")
        day_count = await self._count_days(actor.organization_id, start, end, is_half)
        if day_count <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="The selected range has no working days (weekends/holidays only).")
        # overlap guard against the user's own open requests
        overlap = (await self.db.execute(select(func.count(LeaveRequest.id)).filter(
            LeaveRequest.organization_id == actor.organization_id, LeaveRequest.user_id == user_id,
            LeaveRequest.is_deleted == False, LeaveRequest.status.in_(OPEN_STATUSES),
            LeaveRequest.start_date <= end, LeaveRequest.end_date >= start))).scalar() or 0
        if overlap:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="You already have an overlapping leave/WFH request.")
        if leave_type:
            if leave_type.max_consecutive_days and day_count > leave_type.max_consecutive_days:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Exceeds the {leave_type.max_consecutive_days}-day limit for this type.")
            if leave_type.deducts_balance:
                bals = await self.balances(actor, user_id, start.year)
                row = next((b for b in bals if b["leave_type_id"] == str(leave_type.id)), None)
                available = row["available"] if row else float(leave_type.annual_quota)
                if float(day_count) > available:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Insufficient balance: {available} day(s) available, {day_count} requested.")
        auto_approve = bool(leave_type and not leave_type.requires_approval)
        req = LeaveRequest(organization_id=actor.organization_id, user_id=user_id, request_type=request_type,
                           leave_type_id=leave_type.id if leave_type else None, start_date=start, end_date=end,
                           is_half_day=is_half, half_day_period=data.get("half_day_period") if is_half else None,
                           day_count=day_count, reason=data.get("reason"),
                           status="approved" if auto_approve else "pending",
                           reviewed_by=actor.id if auto_approve else None,
                           reviewed_at=_now() if auto_approve else None, created_by=actor.id)
        self.db.add(req)
        await self.db.flush()
        await self.db.refresh(req)
        if auto_approve:
            await self._mark_attendance(req)
        # notify approver (the requester's manager) of a pending request
        if not auto_approve:
            approver = await self._manager_of(user_id)
            if approver and approver != actor.id:
                await self.notifier.create_notification(
                    organization_id=actor.organization_id, user_id=approver, category="leave",
                    title="Leave request to review",
                    body=f"{await self._name(user_id)} requested {self._label(req)} ({start} → {end}).",
                    link_url="/leaves", priority="high", action_metadata={"request_id": str(req.id)})
        # Workflow: leave applied (+ approved when auto-approved)
        from app.services.workflow_service import WorkflowService
        wf = WorkflowService(self.db)
        await wf.run("leave_applied", req, actor, entity_type="leave")
        if auto_approve:
            await wf.run("leave_approved", req, actor, entity_type="leave")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="LEAVE_APPLIED", resource_type="leave", resource_id=str(req.id),
                                   action_metadata={"type": request_type, "days": float(day_count)})
        return await self._serialize_request(req)

    async def review(self, actor: User, request_id: uuid.UUID, approve: bool, note: str | None = None) -> dict:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can review requests.")
        req = await self._get_request(actor, request_id)
        if req.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request already reviewed.")
        if actor.role == "Manager" and req.user_id not in await self._downline_ids(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in your team.")
        if req.user_id == actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve your own request.")
        req.status = "approved" if approve else "rejected"
        req.reviewed_by = actor.id
        req.reviewed_at = _now()
        req.review_note = note
        self.db.add(req)
        await self.db.flush()
        if approve:
            await self._mark_attendance(req)
            from app.services.workflow_service import WorkflowService
            await WorkflowService(self.db).run("leave_approved", req, actor, entity_type="leave")
        await self.notifier.create_notification(
            organization_id=actor.organization_id, user_id=req.user_id, category="leave",
            title=f"Leave {req.status}", body=f"Your {self._label(req)} request ({req.start_date} → {req.end_date}) was {req.status}.",
            link_url="/leaves", action_metadata={"request_id": str(req.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action=f"LEAVE_{'APPROVED' if approve else 'REJECTED'}",
                                   resource_type="leave", resource_id=str(req.id))
        return await self._serialize_request(req)

    async def cancel(self, actor: User, request_id: uuid.UUID) -> dict:
        req = await self._get_request(actor, request_id)
        if req.user_id != actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own request.")
        if req.status not in ("pending", "approved"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending/approved requests can be cancelled.")
        was_approved = req.status == "approved"
        req.status = "cancelled"
        self.db.add(req)
        await self.db.flush()
        if was_approved:
            await self._unmark_attendance(req)
        return await self._serialize_request(req)

    async def _mark_attendance(self, req: LeaveRequest) -> None:
        """Stamp attendance records `on_leave` (or WFH note) for each covered day."""
        if req.request_type != "leave" or req.is_half_day:
            # half-days and WFH don't fully consume the working day; skip auto-marking
            return
        holidays = await self._holidays_in(req.organization_id, req.start_date, req.end_date)
        cur = req.start_date
        while cur <= req.end_date:
            if cur.weekday() < 5 and cur not in holidays:
                rec = (await self.db.execute(select(AttendanceRecord).filter(
                    AttendanceRecord.organization_id == req.organization_id, AttendanceRecord.user_id == req.user_id,
                    AttendanceRecord.work_date == cur, AttendanceRecord.is_deleted == False))).scalars().first()
                if rec:
                    if not rec.clock_in_at:
                        rec.status = "on_leave"
                        self.db.add(rec)
                else:
                    self.db.add(AttendanceRecord(organization_id=req.organization_id, user_id=req.user_id,
                                                 work_date=cur, status="on_leave", created_by=req.reviewed_by))
            cur += timedelta(days=1)
        await self.db.flush()

    async def _unmark_attendance(self, req: LeaveRequest) -> None:
        rows = list((await self.db.execute(select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == req.organization_id, AttendanceRecord.user_id == req.user_id,
            AttendanceRecord.work_date >= req.start_date, AttendanceRecord.work_date <= req.end_date,
            AttendanceRecord.status == "on_leave", AttendanceRecord.clock_in_at.is_(None),
            AttendanceRecord.is_deleted == False))).scalars().all())
        for r in rows:
            r.is_deleted = True
            self.db.add(r)
        await self.db.flush()

    # ================= Queries =================
    async def _get_request(self, actor: User, request_id: uuid.UUID) -> LeaveRequest:
        r = (await self.db.execute(select(LeaveRequest).filter(
            LeaveRequest.id == request_id, LeaveRequest.organization_id == actor.organization_id,
            LeaveRequest.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        return r

    async def list_requests(self, actor: User, *, scope="mine", status_filter=None, request_type=None,
                            date_from=None, date_to=None, skip=0, limit=100) -> dict:
        q = select(LeaveRequest).filter(LeaveRequest.organization_id == actor.organization_id,
                                        LeaveRequest.is_deleted == False)
        if scope == "mine":
            q = q.filter(LeaveRequest.user_id == actor.id)
        else:  # team / all
            if self._can_admin(actor):
                pass
            elif actor.role == "Manager":
                q = q.filter(LeaveRequest.user_id.in_(list(await self._downline_ids(actor))))
            else:
                q = q.filter(LeaveRequest.user_id == actor.id)
        if status_filter:
            q = q.filter(LeaveRequest.status == status_filter)
        if request_type:
            q = q.filter(LeaveRequest.request_type == request_type)
        if date_from:
            q = q.filter(LeaveRequest.end_date >= date_from)
        if date_to:
            q = q.filter(LeaveRequest.start_date <= date_to)
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(LeaveRequest.start_date.desc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize_request(r) for r in rows], "total": total}

    async def calendar(self, actor: User, date_from: date, date_to: date) -> list[dict]:
        """Team/org leave + WFH (approved & pending) plus holidays in a range."""
        q = select(LeaveRequest).filter(
            LeaveRequest.organization_id == actor.organization_id, LeaveRequest.is_deleted == False,
            LeaveRequest.status.in_(OPEN_STATUSES),
            LeaveRequest.start_date <= date_to, LeaveRequest.end_date >= date_from)
        if not self._can_admin(actor):
            scope = await self._downline_ids(actor) if actor.role == "Manager" else {actor.id}
            q = q.filter(LeaveRequest.user_id.in_(list(scope)))
        rows = list((await self.db.execute(q)).scalars().all())
        names = await self._names({r.user_id for r in rows})
        tnames = await self._type_names({r.leave_type_id for r in rows if r.leave_type_id})
        out = [{"type": "leave", "id": str(r.id), "user_id": str(r.user_id), "user_name": names.get(r.user_id),
                "request_type": r.request_type, "leave_type_name": tnames.get(r.leave_type_id),
                "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
                "is_half_day": r.is_half_day, "day_count": float(r.day_count), "status": r.status} for r in rows]
        for hd in await self._holidays_in(actor.organization_id, date_from, date_to):
            out.append({"type": "holiday", "id": f"h-{hd.isoformat()}", "user_id": None, "user_name": None,
                        "request_type": "holiday", "leave_type_name": None,
                        "start_date": hd.isoformat(), "end_date": hd.isoformat(),
                        "is_half_day": False, "day_count": 1.0, "status": "holiday"})
        out.sort(key=lambda x: x["start_date"])
        return out

    async def dashboard(self, actor: User) -> dict:
        today = date.today()
        # my pending + balance summary
        my_pending = (await self.db.execute(select(func.count(LeaveRequest.id)).filter(
            LeaveRequest.organization_id == actor.organization_id, LeaveRequest.user_id == actor.id,
            LeaveRequest.is_deleted == False, LeaveRequest.status == "pending"))).scalar() or 0
        my_bals = await self.balances(actor, actor.id, today.year)
        available = round(sum(b["available"] for b in my_bals), 1)
        # who is on leave today (scope)
        q = select(LeaveRequest).filter(
            LeaveRequest.organization_id == actor.organization_id, LeaveRequest.is_deleted == False,
            LeaveRequest.status == "approved", LeaveRequest.request_type == "leave",
            LeaveRequest.start_date <= today, LeaveRequest.end_date >= today)
        approvals_q = select(func.count(LeaveRequest.id)).filter(
            LeaveRequest.organization_id == actor.organization_id, LeaveRequest.is_deleted == False,
            LeaveRequest.status == "pending")
        if not self._can_admin(actor):
            scope = await self._downline_ids(actor) if actor.role == "Manager" else {actor.id}
            q = q.filter(LeaveRequest.user_id.in_(list(scope)))
            approvals_q = approvals_q.filter(LeaveRequest.user_id.in_(list(scope)))
        on_leave = list((await self.db.execute(q)).scalars().all())
        names = await self._names({r.user_id for r in on_leave})
        pending_approvals = (await self.db.execute(approvals_q)).scalar() or 0
        # a manager's own pending shouldn't count as something they approve
        if self._is_manager(actor):
            own_pending = (await self.db.execute(select(func.count(LeaveRequest.id)).filter(
                LeaveRequest.organization_id == actor.organization_id, LeaveRequest.user_id == actor.id,
                LeaveRequest.is_deleted == False, LeaveRequest.status == "pending"))).scalar() or 0
            pending_approvals = max(0, pending_approvals - own_pending)
        return {"my_pending": my_pending, "my_available_days": available,
                "pending_approvals": pending_approvals if self._is_manager(actor) else 0,
                "on_leave_today": [{"user_id": str(r.user_id), "name": names.get(r.user_id)} for r in on_leave]}

    async def report(self, actor: User, year: int, user_id=None) -> dict:
        """Per-user leave summary by type for a year (team/org scoped)."""
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            scope = {user_id}
        elif self._can_admin(actor):
            scope = None
        elif actor.role == "Manager":
            scope = await self._downline_ids(actor)
        else:
            scope = {actor.id}
        uq = select(User).filter(User.organization_id == actor.organization_id, User.is_deleted == False)
        if scope is not None:
            uq = uq.filter(User.id.in_(list(scope)))
        users = list((await self.db.execute(uq)).scalars().all())
        rows = []
        for u in users:
            # scope already restricts `users` to viewable ones, so balances() passes its view check
            bals = await self.balances(actor, u.id, year)
            total_used = round(sum(b["used"] for b in bals), 1)
            total_pending = round(sum(b["pending"] for b in bals), 1)
            total_available = round(sum(b["available"] for b in bals), 1)
            rows.append({"user_id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                         "used": total_used, "pending": total_pending, "available": total_available,
                         "by_type": bals})
        rows.sort(key=lambda x: -x["used"])
        return {"year": year, "rows": rows}

    # ---------- helpers ----------
    def _label(self, req: LeaveRequest) -> str:
        return "WFH" if req.request_type == "wfh" else "leave"

    async def _name(self, user_id: uuid.UUID) -> str:
        return (await self._names({user_id})).get(user_id, "A teammate")

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _type_names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(LeaveType.id, LeaveType.name).filter(LeaveType.id.in_(ids)))
        return {tid: name for tid, name in res.all()}

    def _serialize_type(self, t: LeaveType) -> dict:
        return {"id": str(t.id), "name": t.name, "code": t.code, "description": t.description,
                "is_paid": t.is_paid, "annual_quota": float(t.annual_quota),
                "max_consecutive_days": t.max_consecutive_days, "allow_half_day": t.allow_half_day,
                "requires_approval": t.requires_approval, "deducts_balance": t.deducts_balance,
                "color": t.color, "status": t.status, "created_at": t.created_at}

    async def _serialize_request(self, r: LeaveRequest) -> dict:
        names = await self._names({r.user_id, r.reviewed_by})
        tname = (await self._type_names({r.leave_type_id})).get(r.leave_type_id) if r.leave_type_id else None
        return {"id": str(r.id), "user_id": str(r.user_id), "user_name": names.get(r.user_id),
                "request_type": r.request_type, "leave_type_id": str(r.leave_type_id) if r.leave_type_id else None,
                "leave_type_name": tname, "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
                "is_half_day": r.is_half_day, "half_day_period": r.half_day_period, "day_count": float(r.day_count),
                "reason": r.reason, "status": r.status, "reviewed_by_name": names.get(r.reviewed_by) if r.reviewed_by else None,
                "review_note": r.review_note, "created_at": r.created_at}

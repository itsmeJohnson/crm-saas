"""Organization Analytics — a unifying analytics layer over the whole org.

Aggregates the per-domain analytics already produced by other modules
(department/team/branch/performance) and adds the genuinely org-level pieces:
a unified overview, a composite Organization Health score, an org-wide activity
heatmap (weekday × hour), and org metric trends. No new tables — everything is
computed from existing data and delegates to the owning services.
"""
from __future__ import annotations
import csv
import io
import calendar as _cal
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.department import Department
from app.models.team import Team
from app.models.branch import Branch
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.services.department_service import DepartmentService, CONVERTED_LEAD_STATUSES
from app.services.team_service import TeamService
from app.services.branch_territory_service import BranchTerritoryService
from app.services.performance_service import PerformanceService

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class OrganizationAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / scope ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Organization analytics are available to managers and admins only.")

    def _can_admin(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    async def _scope_ids(self, actor: User) -> list[uuid.UUID] | None:
        """None = whole org (OrgAdmin); otherwise a manager's downline + self."""
        if self._can_admin(actor):
            return None
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return list(set(ids) | {actor.id})

    def _range(self, date_from: date | None, date_to: date | None) -> tuple[date, date]:
        today = date.today()
        date_to = date_to or today
        date_from = date_from or date_to.replace(day=1)
        return date_from, date_to

    # ---------- shared metric block ----------
    async def _org_metrics(self, actor: User, date_from: date, date_to: date, scope: list | None) -> dict:
        org = actor.organization_id
        start = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

        lq = select(Lead).filter(Lead.organization_id == org, Lead.is_deleted == False,
                                 Lead.created_at >= start, Lead.created_at <= end)
        if scope is not None:
            lq = lq.filter(Lead.assigned_user_id.in_(scope))
        leads = list((await self.db.execute(lq)).scalars().all())
        total_leads = len(leads)
        converted = revenue = 0
        for l in leads:
            if l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES:
                converted += 1
                if l.value:
                    revenue += float(l.value)

        aq = select(Activity.activity_type, func.count(Activity.id)).filter(
            Activity.organization_id == org, Activity.is_deleted == False,
            Activity.created_at >= start, Activity.created_at <= end)
        if scope is not None:
            aq = aq.filter(Activity.assigned_user_id.in_(scope))
        by_type = {t: n for t, n in (await self.db.execute(aq.group_by(Activity.activity_type))).all()}

        tq = select(func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False, Task.status == "Done",
            Task.updated_at >= start, Task.updated_at <= end)
        if scope is not None:
            tq = tq.filter(Task.assigned_user_id.in_(scope))
        tasks_done = (await self.db.execute(tq)).scalar() or 0

        toq = select(func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False,
            Task.status.in_(["Todo", "InProgress", "Done"]))
        if scope is not None:
            toq = toq.filter(Task.assigned_user_id.in_(scope))
        tasks_total = (await self.db.execute(toq)).scalar() or 0

        return {
            "leads": total_leads, "converted": converted,
            "conversion_rate": round(converted * 100 / total_leads, 1) if total_leads else 0.0,
            "revenue": round(revenue, 2), "calls": by_type.get("Call", 0),
            "activities": sum(by_type.values()), "tasks_completed": tasks_done,
            "task_completion_rate": round(tasks_done * 100 / tasks_total, 1) if tasks_total else 0.0,
        }

    async def _attendance_today(self, actor: User, scope: list | None) -> dict:
        org = actor.organization_id
        today = date.today()
        rq = select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == org, AttendanceRecord.is_deleted == False,
            AttendanceRecord.work_date == today)
        if scope is not None:
            rq = rq.filter(AttendanceRecord.user_id.in_(scope))
        recs = list((await self.db.execute(rq)).scalars().all())
        present = sum(1 for r in recs if r.clock_in_at)
        uq = select(func.count(User.id)).filter(User.organization_id == org, User.is_deleted == False,
                                                User.is_active == True)
        if scope is not None:
            uq = uq.filter(User.id.in_(scope))
        headcount = (await self.db.execute(uq)).scalar() or 0
        on_leave = (await self.db.execute(select(func.count(func.distinct(LeaveRequest.user_id))).filter(
            LeaveRequest.organization_id == org, LeaveRequest.is_deleted == False,
            LeaveRequest.status == "approved", LeaveRequest.request_type == "leave",
            LeaveRequest.start_date <= today, LeaveRequest.end_date >= today,
            *([LeaveRequest.user_id.in_(scope)] if scope is not None else [])))).scalar() or 0
        return {"headcount": headcount, "present_today": present,
                "attendance_rate": round(present * 100 / headcount, 1) if headcount else 0.0,
                "on_leave_today": on_leave}

    # ================= Overview =================
    async def overview(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        date_from, date_to = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        org = actor.organization_id
        metrics = await self._org_metrics(actor, date_from, date_to, scope)
        att = await self._attendance_today(actor, scope)
        departments = (await self.db.execute(select(func.count(Department.id)).filter(
            Department.organization_id == org, Department.is_deleted == False, Department.status == "active"))).scalar() or 0
        teams = (await self.db.execute(select(func.count(Team.id)).filter(
            Team.organization_id == org, Team.is_deleted == False, Team.status == "active"))).scalar() or 0
        branches = (await self.db.execute(select(func.count(Branch.id)).filter(
            Branch.organization_id == org, Branch.is_deleted == False, Branch.status == "active"))).scalar() or 0
        pending_leaves = (await self.db.execute(select(func.count(LeaveRequest.id)).filter(
            LeaveRequest.organization_id == org, LeaveRequest.is_deleted == False,
            LeaveRequest.status == "pending", *([LeaveRequest.user_id.in_(scope)] if scope is not None else [])))).scalar() or 0
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "departments": departments, "teams": teams, "branches": branches,
                "pending_leaves": pending_leaves, **att, **metrics}

    # ================= Organization Health =================
    async def health(self, actor: User) -> dict:
        """Composite 0-100 health score blending attendance, target attainment,
        task completion and lead conversion."""
        self._require_manager(actor)
        scope = await self._scope_ids(actor)
        today = date.today()
        month_start = today.replace(day=1)
        metrics = await self._org_metrics(actor, month_start, today, scope)
        att = await self._attendance_today(actor, scope)
        # target attainment (unified target dashboard)
        from app.services.target_service import TargetService
        try:
            tdash = await TargetService(self.db).dashboard(actor)
            target_score = min(100.0, float(tdash.get("avg_attainment", 0)))
        except Exception:
            target_score = 0.0
        components = [
            {"name": "Attendance", "score": att["attendance_rate"], "weight": 1},
            {"name": "Target attainment", "score": target_score, "weight": 2},
            {"name": "Task completion", "score": metrics["task_completion_rate"], "weight": 1},
            {"name": "Lead conversion", "score": min(100.0, metrics["conversion_rate"]), "weight": 2},
        ]
        wsum = sum(c["score"] * c["weight"] for c in components)
        wtot = sum(c["weight"] for c in components)
        score = round(wsum / wtot, 1) if wtot else 0.0
        rating = "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair" if score >= 40 else "Needs attention"
        return {"score": score, "rating": rating, "components": components}

    # ================= Leaderboard (reuse) =================
    async def leaderboard(self, actor: User, metric: str, date_from=None, date_to=None, limit: int = 10) -> list[dict]:
        self._require_manager(actor)
        date_from, date_to = self._range(date_from, date_to)
        return await PerformanceService(self.db).leaderboard(actor, metric, date_from, date_to, limit=limit)

    # ================= Heatmap =================
    async def heatmap(self, actor: User, date_from=None, date_to=None) -> dict:
        """Org activity heatmap: counts per weekday (0=Mon) × hour (0-23)."""
        self._require_manager(actor)
        date_from, date_to = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        start = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
        q = select(Activity.created_at).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.created_at >= start, Activity.created_at <= end)
        if scope is not None:
            q = q.filter(Activity.assigned_user_id.in_(scope))
        grid = [[0] * 24 for _ in range(7)]
        peak = {"weekday": 0, "hour": 0, "count": 0}
        for (created,) in (await self.db.execute(q)).all():
            if not created:
                continue
            dt = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            wd, hr = dt.weekday(), dt.hour
            grid[wd][hr] += 1
            if grid[wd][hr] > peak["count"]:
                peak = {"weekday": wd, "hour": hr, "count": grid[wd][hr]}
        return {"weekdays": WEEKDAYS, "grid": grid,
                "peak": {**peak, "weekday_label": WEEKDAYS[peak["weekday"]]}}

    # ================= Trend =================
    async def trend(self, actor: User, granularity: str = "monthly", count: int = 6) -> dict:
        self._require_manager(actor)
        if granularity not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="granularity must be daily|weekly|monthly.")
        count = max(1, min(count, 24))
        scope = await self._scope_ids(actor)
        today = date.today()
        buckets: list[tuple[date, date, str]] = []
        if granularity == "daily":
            for i in range(count - 1, -1, -1):
                d = today - timedelta(days=i)
                buckets.append((d, d, d.strftime("%d %b")))
        elif granularity == "weekly":
            monday = today - timedelta(days=today.weekday())
            for i in range(count - 1, -1, -1):
                s = monday - timedelta(days=7 * i)
                buckets.append((s, s + timedelta(days=6), f"W{s.isocalendar()[1]}"))
        else:
            y, m = today.year, today.month
            months = []
            for _ in range(count):
                months.append((y, m))
                m -= 1
                if m == 0:
                    m = 12; y -= 1
            for (yy, mm) in reversed(months):
                s = date(yy, mm, 1)
                e = date(yy, mm, _cal.monthrange(yy, mm)[1])
                buckets.append((s, e, s.strftime("%b %Y")))
        series = []
        for (s, e, label) in buckets:
            m = await self._org_metrics(actor, s, e, scope)
            series.append({"label": label, "leads": m["leads"], "converted": m["converted"],
                           "revenue": m["revenue"], "activities": m["activities"],
                           "tasks_completed": m["tasks_completed"]})
        return {"granularity": granularity, "series": series}

    # ================= Domain analytics passthrough =================
    async def domain(self, actor: User, kind: str, date_from=None, date_to=None) -> list[dict]:
        self._require_manager(actor)
        df = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc) if date_from else None
        dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc) if date_to else None
        if kind == "department":
            return await DepartmentService(self.db).analytics(actor, date_from=df, date_to=dt)
        if kind == "team":
            return await TeamService(self.db).analytics(actor, date_from=df, date_to=dt)
        if kind == "branch":
            return await BranchTerritoryService(self.db).branch_analytics(actor, date_from=df, date_to=dt)
        if kind == "territory":
            return await BranchTerritoryService(self.db).territory_analytics(actor, date_from=df, date_to=dt)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="kind must be department|team|branch|territory.")

    # ================= Export =================
    async def export_csv(self, actor: User, date_from=None, date_to=None) -> str:
        self._require_manager(actor)
        date_from, date_to = self._range(date_from, date_to)
        ov = await self.overview(actor, date_from, date_to)
        depts = await self.domain(actor, "department", date_from, date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Organization Analytics", f"{date_from} to {date_to}"])
        w.writerow([])
        w.writerow(["Metric", "Value"])
        for k in ("headcount", "present_today", "attendance_rate", "on_leave_today", "departments",
                  "teams", "branches", "leads", "converted", "conversion_rate", "revenue", "calls",
                  "activities", "tasks_completed", "task_completion_rate", "pending_leaves"):
            w.writerow([k, ov.get(k)])
        w.writerow([])
        w.writerow(["Department", "Members", "Leads Converted", "Revenue", "Calls", "Activities"])
        for d in depts:
            w.writerow([d.get("name"), d.get("member_count"), d.get("leads_converted"),
                        d.get("revenue"), d.get("calls_made"), d.get("activities")])
        return buf.getvalue()

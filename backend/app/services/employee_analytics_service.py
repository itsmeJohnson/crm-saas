"""Employee Analytics — a unified workforce analytics layer.

Composes the per-user metrics that already exist (PerformanceService over leads/
activities/tasks/payments/attendance) with attendance, leave and training data
into one employee-centric surface: a productivity roster, per-employee deep dive,
attendance & performance trends, manager/department/branch comparisons,
leaderboards and an activity heatmap. The only new data source is
`employee_trainings` (training scores); everything else is reused. Manager-scoped
to the caller's downline; admins see the whole org.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.task import Task
from app.models.activity import Activity
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.models.employee_training import EmployeeTraining

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GRANULARITIES = ("daily", "weekly", "monthly")
PRESENT_STATUSES = ("present", "late", "half_day")
COMPARE_KIND = ("department", "branch")
TRAINING_STATUSES = ("planned", "in_progress", "completed")


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class EmployeeAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / scope / window ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Employee analytics are available to managers and admins only.")

    def _can_admin(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    async def _scope_ids(self, actor: User) -> set | None:
        if self._can_admin(actor):
            return None
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return set(ids) | {actor.id}

    def _range(self, date_from: date | None, date_to: date | None) -> tuple[date, date]:
        today = date.today()
        to_d = date_to or today
        from_d = date_from or (to_d - timedelta(days=29))
        return from_d, to_d

    async def _employees(self, actor: User, scope: set | None) -> list[User]:
        q = select(User).filter(User.organization_id == actor.organization_id, User.is_deleted == False,
                                User.is_active == True, User.role != "SuperAdmin")
        if scope is not None:
            q = q.filter(User.id.in_(list(scope)))
        return list((await self.db.execute(q)).scalars().all())

    @staticmethod
    def _rate(part, whole) -> float:
        return round(part * 100 / whole, 1) if whole else 0.0

    # ---------- batch metric helpers ----------
    async def _attendance(self, org, user_ids: list, fd: date, td: date) -> dict:
        rows = (await self.db.execute(select(
            AttendanceRecord.user_id, AttendanceRecord.status, func.count(AttendanceRecord.id)).filter(
            AttendanceRecord.organization_id == org, AttendanceRecord.is_deleted == False,
            AttendanceRecord.user_id.in_(user_ids) if user_ids else False,
            AttendanceRecord.work_date >= fd, AttendanceRecord.work_date <= td)
            .group_by(AttendanceRecord.user_id, AttendanceRecord.status))).all() if user_ids else []
        out: dict = {}
        for uid, st, n in rows:
            b = out.setdefault(uid, {"present": 0, "late": 0, "half_day": 0, "absent": 0, "on_leave": 0, "holiday": 0})
            b[st] = b.get(st, 0) + n
        for uid, b in out.items():
            worked = b["present"] + b["late"] + b["half_day"]
            base = worked + b["absent"]
            b["working_days"] = base
            b["attendance_rate"] = self._rate(worked, base)
        return out

    async def _tasks(self, org, user_ids: list, fd: date, td: date) -> dict:
        start = datetime.combine(fd, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(td, time.max).replace(tzinfo=timezone.utc)
        rows = (await self.db.execute(select(
            Task.assigned_user_id, Task.status, func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False,
            Task.assigned_user_id.in_(user_ids) if user_ids else False,
            Task.created_at >= start, Task.created_at <= end)
            .group_by(Task.assigned_user_id, Task.status))).all() if user_ids else []
        out: dict = {}
        for uid, st, n in rows:
            b = out.setdefault(uid, {"total": 0, "done": 0})
            b["total"] += n
            if st == "Done":
                b["done"] += n
        for uid, b in out.items():
            b["completion_rate"] = self._rate(b["done"], b["total"])
        return out

    async def _leave(self, org, user_ids: list, fd: date, td: date) -> dict:
        rows = (await self.db.execute(select(
            LeaveRequest.user_id, func.coalesce(func.sum(LeaveRequest.day_count), 0)).filter(
            LeaveRequest.organization_id == org, LeaveRequest.is_deleted == False,
            LeaveRequest.status == "approved", LeaveRequest.user_id.in_(user_ids) if user_ids else False,
            LeaveRequest.start_date <= td, LeaveRequest.end_date >= fd)
            .group_by(LeaveRequest.user_id))).all() if user_ids else []
        return {uid: float(days or 0) for uid, days in rows}

    async def _training(self, org, user_ids: list) -> dict:
        if not user_ids:
            return {}
        recs = list((await self.db.execute(select(EmployeeTraining).filter(
            EmployeeTraining.organization_id == org, EmployeeTraining.is_deleted == False,
            EmployeeTraining.user_id.in_(user_ids)))).scalars().all())
        out: dict = {}
        for r in recs:
            b = out.setdefault(r.user_id, {"count": 0, "completed": 0, "score_sum": 0, "scored": 0})
            b["count"] += 1
            if r.status == "completed":
                b["completed"] += 1
            if r.score is not None:
                b["score_sum"] += r.score
                b["scored"] += 1
        for uid, b in out.items():
            b["avg_score"] = round(b["score_sum"] / b["scored"], 1) if b["scored"] else 0.0
        return out

    def _productivity_score(self, task_rate, attendance_rate, conversion_rate, activities) -> float:
        return round(0.30 * task_rate + 0.30 * attendance_rate + 0.20 * conversion_rate
                     + 0.20 * min(100, activities * 5), 1)

    # ================= roster =================
    async def roster(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        fd, td = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        employees = await self._employees(actor, scope)
        uids = [u.id for u in employees]
        att = await self._attendance(org, uids, fd, td)
        tsk = await self._tasks(org, uids, fd, td)
        lve = await self._leave(org, uids, fd, td)
        trn = await self._training(org, uids)
        from app.services.performance_service import PerformanceService
        perf = PerformanceService(self.db)
        rows = []
        for u in employees:
            m = await perf._user_metrics(org, u.id, fd, td)
            a = att.get(u.id, {})
            t = tsk.get(u.id, {})
            tr = trn.get(u.id, {})
            attendance_rate = a.get("attendance_rate", 0.0)
            task_rate = t.get("completion_rate", 0.0)
            score = self._productivity_score(task_rate, attendance_rate, m.get("conversion_rate", 0.0), m.get("activities", 0))
            rows.append({
                "user_id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                "role": u.role, "calls": m.get("calls_made", 0), "leads_converted": m.get("leads_converted", 0),
                "conversion_rate": m.get("conversion_rate", 0.0), "revenue": m.get("sales_revenue", 0.0),
                "activities": m.get("activities", 0), "tasks_total": t.get("total", 0), "tasks_done": t.get("done", 0),
                "task_completion_rate": task_rate, "attendance_rate": attendance_rate,
                "present_days": a.get("present", 0) + a.get("late", 0) + a.get("half_day", 0),
                "leave_days": lve.get(u.id, 0.0), "training_score": tr.get("avg_score", 0.0),
                "productivity_score": score,
            })
        rows.sort(key=lambda r: -r["productivity_score"])
        return {"from": fd.isoformat(), "to": td.isoformat(), "headcount": len(rows), "employees": rows}

    # ================= employee deep-dive =================
    async def employee(self, actor: User, user_id: uuid.UUID, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        fd, td = self._range(date_from, date_to)
        u = await self._get_scoped_user(actor, user_id)
        att = (await self._attendance(org, [u.id], fd, td)).get(u.id, {})
        tsk = (await self._tasks(org, [u.id], fd, td)).get(u.id, {})
        lve = (await self._leave(org, [u.id], fd, td)).get(u.id, 0.0)
        trn = (await self._training(org, [u.id])).get(u.id, {})
        from app.services.performance_service import PerformanceService
        m = await PerformanceService(self.db)._user_metrics(org, u.id, fd, td)
        score = self._productivity_score(tsk.get("completion_rate", 0.0), att.get("attendance_rate", 0.0),
                                         m.get("conversion_rate", 0.0), m.get("activities", 0))
        trainings = await self.list_trainings(actor, user_id=u.id)
        return {
            "user_id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
            "role": u.role, "from": fd.isoformat(), "to": td.isoformat(),
            "productivity_score": score,
            "lead_productivity": {"leads_converted": m.get("leads_converted", 0), "conversion_rate": m.get("conversion_rate", 0.0),
                                  "revenue": m.get("sales_revenue", 0.0)},
            "call_productivity": {"calls": m.get("calls_made", 0), "activities": m.get("activities", 0)},
            "task_completion": {"total": tsk.get("total", 0), "done": tsk.get("done", 0),
                                "completion_rate": tsk.get("completion_rate", 0.0)},
            "attendance": {**{k: att.get(k, 0) for k in ("present", "late", "half_day", "absent", "on_leave")},
                           "attendance_rate": att.get("attendance_rate", 0.0), "working_days": att.get("working_days", 0)},
            "leave_analysis": {"approved_days": lve},
            "training": {"count": trn.get("count", 0), "completed": trn.get("completed", 0),
                         "avg_score": trn.get("avg_score", 0.0), "records": trainings},
        }

    async def _get_scoped_user(self, actor: User, user_id: uuid.UUID) -> User:
        scope = await self._scope_ids(actor)
        if scope is not None and user_id not in scope:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That employee is outside your team.")
        u = (await self.db.execute(select(User).filter(
            User.id == user_id, User.organization_id == actor.organization_id, User.is_deleted == False))).scalars().first()
        if not u:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        return u

    # ================= trends =================
    async def attendance_trend(self, actor: User, user_id=None, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        fd, td = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        if user_id:
            await self._get_scoped_user(actor, user_id)
            uids = [user_id]
        else:
            uids = [u.id for u in await self._employees(actor, scope)]
        rows = (await self.db.execute(select(
            AttendanceRecord.work_date, AttendanceRecord.status, func.count(AttendanceRecord.id)).filter(
            AttendanceRecord.organization_id == org, AttendanceRecord.is_deleted == False,
            AttendanceRecord.user_id.in_(uids) if uids else False,
            AttendanceRecord.work_date >= fd, AttendanceRecord.work_date <= td)
            .group_by(AttendanceRecord.work_date, AttendanceRecord.status))).all() if uids else []
        buckets: dict = {}
        for wd, st, n in rows:
            b = buckets.setdefault(wd.isoformat(), {"date": wd.isoformat(), "present": 0, "late": 0,
                                                    "half_day": 0, "absent": 0, "on_leave": 0})
            b[st] = b.get(st, 0) + n
        series = [buckets[k] for k in sorted(buckets)]
        return {"from": fd.isoformat(), "to": td.isoformat(), "series": series}

    async def performance_trend(self, actor: User, user_id: uuid.UUID, granularity="weekly", count=8) -> dict:
        self._require_manager(actor)
        if granularity not in GRANULARITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"granularity must be one of {list(GRANULARITIES)}")
        await self._get_scoped_user(actor, user_id)
        from app.services.performance_service import PerformanceService
        return await PerformanceService(self.db).period_performance(actor, user_id, granularity, count)

    # ================= comparisons =================
    async def manager_comparison(self, actor: User, date_from=None, date_to=None) -> dict:
        """Compare managers by their team's aggregate productivity."""
        self._require_manager(actor)
        org = actor.organization_id
        fd, td = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        employees = await self._employees(actor, scope)
        managers = {u.id: u for u in employees if u.role in ("Manager", "OrgAdmin")}
        uids = [u.id for u in employees]
        att = await self._attendance(org, uids, fd, td)
        tsk = await self._tasks(org, uids, fd, td)
        from app.services.performance_service import PerformanceService
        perf = PerformanceService(self.db)
        groups: dict = {}
        for u in employees:
            mgr = u.reporting_to_id
            if mgr not in managers:
                continue
            m = await perf._user_metrics(org, u.id, fd, td)
            g = groups.setdefault(mgr, {"team_size": 0, "leads_converted": 0, "calls": 0, "revenue": 0.0,
                                        "activities": 0, "task_rate_sum": 0.0, "att_rate_sum": 0.0})
            g["team_size"] += 1
            g["leads_converted"] += m.get("leads_converted", 0)
            g["calls"] += m.get("calls_made", 0)
            g["revenue"] += m.get("sales_revenue", 0.0)
            g["activities"] += m.get("activities", 0)
            g["task_rate_sum"] += tsk.get(u.id, {}).get("completion_rate", 0.0)
            g["att_rate_sum"] += att.get(u.id, {}).get("attendance_rate", 0.0)
        rows = []
        for mgr_id, g in groups.items():
            n = g["team_size"]
            mgr = managers[mgr_id]
            rows.append({"manager_id": str(mgr_id),
                         "manager_name": f"{mgr.first_name or ''} {mgr.last_name or ''}".strip() or mgr.email,
                         "team_size": n, "leads_converted": g["leads_converted"], "calls": g["calls"],
                         "revenue": round(g["revenue"], 2), "activities": g["activities"],
                         "avg_task_completion": round(g["task_rate_sum"] / n, 1) if n else 0.0,
                         "avg_attendance": round(g["att_rate_sum"] / n, 1) if n else 0.0})
        rows.sort(key=lambda r: -r["revenue"])
        return {"managers": rows}

    async def structure_comparison(self, actor: User, kind: str, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        if kind not in COMPARE_KIND:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"kind must be one of {list(COMPARE_KIND)}")
        from app.services.org_analytics_service import OrganizationAnalyticsService
        try:
            rows = await OrganizationAnalyticsService(self.db).domain(actor, kind, date_from=date_from, date_to=date_to)
        except HTTPException:
            rows = []
        return {"kind": kind, "rows": rows}

    # ================= leaderboard / heatmap =================
    async def leaderboard(self, actor: User, metric="leads_converted", date_from=None, date_to=None, limit=20) -> list[dict]:
        self._require_manager(actor)
        fd, td = self._range(date_from, date_to)
        from app.services.performance_service import PerformanceService
        return await PerformanceService(self.db).leaderboard(actor, metric, fd, td, limit=limit)

    async def heatmap(self, actor: User, user_id=None, date_from=None, date_to=None) -> dict:
        """Activity heatmap (weekday × hour) for the scoped workforce or one user."""
        self._require_manager(actor)
        org = actor.organization_id
        fd, td = self._range(date_from, date_to)
        scope = await self._scope_ids(actor)
        if user_id:
            await self._get_scoped_user(actor, user_id)
            uids = [user_id]
        else:
            uids = [u.id for u in await self._employees(actor, scope)]
        start = datetime.combine(fd, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(td, time.max).replace(tzinfo=timezone.utc)
        acts = list((await self.db.execute(select(Activity.created_at).filter(
            Activity.organization_id == org, Activity.is_deleted == False,
            Activity.assigned_user_id.in_(uids) if uids else False,
            Activity.created_at >= start, Activity.created_at <= end))).scalars().all()) if uids else []
        grid = [[0] * 24 for _ in range(7)]
        peak = {"weekday": 0, "hour": 0, "count": 0}
        for c in acts:
            dt = _aware(c)
            grid[dt.weekday()][dt.hour] += 1
            if grid[dt.weekday()][dt.hour] > peak["count"]:
                peak = {"weekday": dt.weekday(), "hour": dt.hour, "count": grid[dt.weekday()][dt.hour]}
        peak["weekday_label"] = WEEKDAYS[peak["weekday"]]
        return {"weekdays": WEEKDAYS, "grid": grid, "peak": peak, "total": len(acts)}

    # ================= training CRUD =================
    async def list_trainings(self, actor: User, user_id=None) -> list[dict]:
        q = select(EmployeeTraining).filter(EmployeeTraining.organization_id == actor.organization_id,
                                            EmployeeTraining.is_deleted == False)
        if user_id:
            q = q.filter(EmployeeTraining.user_id == user_id)
        else:
            scope = await self._scope_ids(actor)
            if scope is not None:
                q = q.filter(EmployeeTraining.user_id.in_(list(scope)))
        rows = (await self.db.execute(q.order_by(EmployeeTraining.created_at.desc()))).scalars().all()
        return [self._serialize_training(t) for t in rows]

    async def create_training(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        st = data.get("status") or "completed"
        if st not in TRAINING_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"status must be one of {list(TRAINING_STATUSES)}")
        score = data.get("score")
        if score is not None and not (0 <= int(score) <= 100):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="score must be 0-100.")
        await self._get_scoped_user(actor, data["user_id"])
        t = EmployeeTraining(organization_id=actor.organization_id, user_id=data["user_id"], name=data["name"],
                             category=data.get("category"), status=st,
                             score=int(score) if score is not None else None,
                             completed_at=datetime.now(timezone.utc) if st == "completed" else None,
                             created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return self._serialize_training(t)

    async def update_training(self, actor: User, training_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        t = (await self.db.execute(select(EmployeeTraining).filter(
            EmployeeTraining.id == training_id, EmployeeTraining.organization_id == actor.organization_id,
            EmployeeTraining.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training not found")
        if "name" in data and data["name"]:
            t.name = data["name"]
        if "category" in data:
            t.category = data["category"]
        if "status" in data and data["status"]:
            if data["status"] not in TRAINING_STATUSES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
            t.status = data["status"]
            t.completed_at = datetime.now(timezone.utc) if data["status"] == "completed" else t.completed_at
        if "score" in data:
            s = data["score"]
            if s is not None and not (0 <= int(s) <= 100):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="score must be 0-100.")
            t.score = int(s) if s is not None else None
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return self._serialize_training(t)

    async def delete_training(self, actor: User, training_id: uuid.UUID) -> None:
        self._require_manager(actor)
        t = (await self.db.execute(select(EmployeeTraining).filter(
            EmployeeTraining.id == training_id, EmployeeTraining.organization_id == actor.organization_id,
            EmployeeTraining.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training not found")
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    def _serialize_training(self, t: EmployeeTraining) -> dict:
        return {"id": str(t.id), "user_id": str(t.user_id), "name": t.name, "category": t.category,
                "status": t.status, "score": t.score,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None}

    # ================= dashboard / report / export =================
    async def dashboard(self, actor: User) -> dict:
        r = await self.roster(actor, None, None)
        emps = r["employees"]
        n = len(emps)
        avg_prod = round(sum(e["productivity_score"] for e in emps) / n, 1) if n else 0.0
        avg_att = round(sum(e["attendance_rate"] for e in emps) / n, 1) if n else 0.0
        avg_train = round(sum(e["training_score"] for e in emps) / n, 1) if n else 0.0
        top = emps[0] if emps else None
        return {"headcount": n, "avg_productivity": avg_prod, "avg_attendance": avg_att,
                "avg_training_score": avg_train,
                "top_performer": {"name": top["name"], "productivity_score": top["productivity_score"]} if top else None}

    async def export_csv(self, actor: User, date_from=None, date_to=None) -> str:
        r = await self.roster(actor, date_from, date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Employee analytics", f"{r['from']} → {r['to']}", f"headcount={r['headcount']}"])
        w.writerow([])
        w.writerow(["Employee", "Role", "Productivity", "Leads won", "Conv %", "Calls", "Activities",
                    "Tasks done", "Task %", "Attendance %", "Leave days", "Training"])
        for e in r["employees"]:
            w.writerow([e["name"], e["role"], e["productivity_score"], e["leads_converted"], e["conversion_rate"],
                        e["calls"], e["activities"], e["tasks_done"], e["task_completion_rate"],
                        e["attendance_rate"], e["leave_days"], e["training_score"]])
        return buf.getvalue()

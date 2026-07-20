"""Performance Management service.

A unifying per-user performance layer over data the other modules already
produce — leads (sales & conversion), activities (calls), tasks, customer
payments (recovery), and attendance records (attendance score). It does NOT
replace the sales analytics_service or the org-level PerformanceTarget; it adds
first-class KPIs, per-user goals/targets, achievements, leaderboards, a
composite scorecard, and daily/weekly/monthly trends.
"""
from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.customer_payment import CustomerPayment
from app.models.attendance import AttendanceRecord
from app.models.performance import (
    PerformanceKPI, PerformanceGoal, PerformanceAchievement, PERFORMANCE_METRICS,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}
UNIT_BY_METRIC = {
    "calls_made": "count", "leads_converted": "count", "conversion_rate": "percent",
    "sales_revenue": "currency", "recovery_amount": "currency", "tasks_completed": "count",
    "activities": "count", "attendance_score": "percent",
}
# Sensible starter KPI set (name, code, metric, weight, unit)
DEFAULT_KPIS = [
    ("Calls Made", "CALLS", "calls_made", 1),
    ("Leads Converted", "CONV", "leads_converted", 2),
    ("Conversion Rate", "CVR", "conversion_rate", 2),
    ("Sales Revenue", "SALES", "sales_revenue", 3),
    ("Recovery Collected", "RECOV", "recovery_amount", 2),
    ("Tasks Completed", "TASKS", "tasks_completed", 1),
    ("Attendance Score", "ATT", "attendance_score", 1),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


class PerformanceService:
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can manage KPIs.")

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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view this user's performance.")

    async def _scope_ids(self, actor: User) -> set[uuid.UUID] | None:
        if self._can_admin(actor):
            return None
        if actor.role == "Manager":
            return await self._downline_ids(actor)
        return {actor.id}

    # ================= Metric computation =================
    async def _user_metrics(self, org_id, user_id, date_from: date, date_to: date) -> dict:
        start = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
        # Leads assigned to the user (sales + conversion)
        leads = list((await self.db.execute(select(Lead).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False,
            Lead.assigned_user_id == user_id, Lead.created_at >= start, Lead.created_at <= end))).scalars().all())
        total_leads = len(leads)
        converted = 0
        revenue = 0.0
        for l in leads:
            if l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES:
                converted += 1
                if l.value:
                    revenue += float(l.value)
        # Activities (calls + all comms)
        act_rows = (await self.db.execute(select(Activity.activity_type, func.count(Activity.id)).filter(
            Activity.organization_id == org_id, Activity.is_deleted == False,
            Activity.assigned_user_id == user_id, Activity.created_at >= start, Activity.created_at <= end)
            .group_by(Activity.activity_type))).all()
        by_type = {t: n for t, n in act_rows}
        # Tasks completed
        tasks_done = (await self.db.execute(select(func.count(Task.id)).filter(
            Task.organization_id == org_id, Task.is_deleted == False, Task.assigned_user_id == user_id,
            Task.status == "Done", Task.updated_at >= start, Task.updated_at <= end))).scalar() or 0
        # Recovery: payments recorded by the user in the period
        recovery = (await self.db.execute(select(func.coalesce(func.sum(CustomerPayment.amount), 0)).filter(
            CustomerPayment.organization_id == org_id, CustomerPayment.is_deleted == False,
            CustomerPayment.created_by == user_id,
            or_(CustomerPayment.paid_at.is_(None), CustomerPayment.paid_at >= start),
            or_(CustomerPayment.paid_at.is_(None), CustomerPayment.paid_at <= end)))).scalar() or 0
        # Attendance score
        att_rows = (await self.db.execute(select(AttendanceRecord.status, AttendanceRecord.clock_in_at).filter(
            AttendanceRecord.organization_id == org_id, AttendanceRecord.is_deleted == False,
            AttendanceRecord.user_id == user_id, AttendanceRecord.work_date >= date_from,
            AttendanceRecord.work_date <= date_to))).all()
        counted = [r for r in att_rows if r[0] in ("present", "late", "half_day", "absent")]
        present = sum(1 for r in counted if r[1] is not None or r[0] in ("present", "late", "half_day"))
        attendance_score = round(present * 100 / len(counted), 1) if counted else 0.0
        conversion_rate = round(converted * 100 / total_leads, 1) if total_leads else 0.0
        return {
            "calls_made": by_type.get("Call", 0), "leads_converted": converted,
            "conversion_rate": conversion_rate, "sales_revenue": round(revenue, 2),
            "recovery_amount": round(float(recovery), 2), "tasks_completed": tasks_done,
            "activities": sum(by_type.values()), "attendance_score": attendance_score,
        }

    # ================= KPI catalog =================
    async def _get_kpi(self, actor: User, kpi_id: uuid.UUID) -> PerformanceKPI:
        k = (await self.db.execute(select(PerformanceKPI).filter(
            PerformanceKPI.id == kpi_id, PerformanceKPI.organization_id == actor.organization_id,
            PerformanceKPI.is_deleted == False))).scalars().first()
        if not k:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
        return k

    async def list_kpis(self, actor: User, status_filter=None) -> list[dict]:
        q = select(PerformanceKPI).filter(PerformanceKPI.organization_id == actor.organization_id,
                                          PerformanceKPI.is_deleted == False)
        if status_filter:
            q = q.filter(PerformanceKPI.status == status_filter)
        rows = list((await self.db.execute(q.order_by(PerformanceKPI.name.asc()))).scalars().all())
        return [self._serialize_kpi(k) for k in rows]

    async def create_kpi(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        metric = data["metric"]
        if metric not in PERFORMANCE_METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {list(PERFORMANCE_METRICS)}")
        if data.get("code"):
            dup = (await self.db.execute(select(PerformanceKPI.id).filter(
                PerformanceKPI.organization_id == actor.organization_id, PerformanceKPI.code == data["code"],
                PerformanceKPI.is_deleted == False))).scalar()
            if dup:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"KPI code '{data['code']}' already exists.")
        k = PerformanceKPI(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                           metric=metric, description=data.get("description"),
                           unit=data.get("unit") or UNIT_BY_METRIC.get(metric, "count"),
                           weight=_d(data.get("weight", 1)), higher_is_better=bool(data.get("higher_is_better", True)),
                           status=data.get("status", "active"), color=data.get("color"), created_by=actor.id)
        self.db.add(k)
        await self.db.flush()
        await self.db.refresh(k)
        return self._serialize_kpi(k)

    async def update_kpi(self, actor: User, kpi_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        k = await self._get_kpi(actor, kpi_id)
        if "metric" in data and data["metric"] not in PERFORMANCE_METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {list(PERFORMANCE_METRICS)}")
        for f in ("name", "code", "metric", "description", "unit", "higher_is_better", "status", "color"):
            if f in data:
                setattr(k, f, data[f])
        if "weight" in data:
            k.weight = _d(data["weight"])
        self.db.add(k)
        await self.db.flush()
        await self.db.refresh(k)
        return self._serialize_kpi(k)

    async def delete_kpi(self, actor: User, kpi_id: uuid.UUID) -> None:
        self._require_admin(actor)
        k = await self._get_kpi(actor, kpi_id)
        k.is_deleted = True
        self.db.add(k)
        await self.db.flush()

    async def seed_default_kpis(self, actor: User) -> dict:
        self._require_admin(actor)
        created = 0
        for name, code, metric, weight in DEFAULT_KPIS:
            exists = (await self.db.execute(select(PerformanceKPI.id).filter(
                PerformanceKPI.organization_id == actor.organization_id, PerformanceKPI.code == code,
                PerformanceKPI.is_deleted == False))).scalar()
            if exists:
                continue
            self.db.add(PerformanceKPI(organization_id=actor.organization_id, name=name, code=code, metric=metric,
                                       unit=UNIT_BY_METRIC.get(metric, "count"), weight=_d(weight),
                                       status="active", created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"created": created}

    # ================= Goals (per-user targets) =================
    async def _get_goal(self, actor: User, goal_id: uuid.UUID) -> PerformanceGoal:
        g = (await self.db.execute(select(PerformanceGoal).filter(
            PerformanceGoal.id == goal_id, PerformanceGoal.organization_id == actor.organization_id,
            PerformanceGoal.is_deleted == False))).scalars().first()
        if not g:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        return g

    async def create_goal(self, actor: User, data: dict) -> dict:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can set performance goals.")
        user_id = data["user_id"]
        # managers may only set goals for their downline
        if actor.role == "Manager" and user_id not in await self._downline_ids(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not in your team.")
        u = (await self.db.execute(select(User.id).filter(
            User.id == user_id, User.organization_id == actor.organization_id, User.is_deleted == False))).scalar()
        if not u:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found in this org.")
        kpi = await self._get_kpi(actor, data["kpi_id"])
        if data["end_date"] < data["start_date"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date is before start_date.")
        g = PerformanceGoal(organization_id=actor.organization_id, user_id=user_id, kpi_id=kpi.id,
                            period=data.get("period", "monthly"), target_value=_d(data["target_value"]),
                            start_date=data["start_date"], end_date=data["end_date"],
                            status=data.get("status", "active"), created_by=actor.id)
        self.db.add(g)
        await self.db.flush()
        await self.db.refresh(g)
        await self.notifier.create_notification(
            organization_id=actor.organization_id, user_id=user_id, category="performance",
            title="New performance goal", body=f"A {kpi.name} target of {data['target_value']} was set for you.",
            link_url="/performance", action_metadata={"goal_id": str(g.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="PERFORMANCE_GOAL_SET", resource_type="performance", resource_id=str(g.id),
                                   action_metadata={"kpi": kpi.name, "target": float(g.target_value)})
        return await self._serialize_goal(g)

    async def update_goal(self, actor: User, goal_id: uuid.UUID, data: dict) -> dict:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can edit goals.")
        g = await self._get_goal(actor, goal_id)
        if actor.role == "Manager" and g.user_id not in await self._downline_ids(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not in your team.")
        for f in ("period", "start_date", "end_date", "status"):
            if f in data and data[f] is not None:
                setattr(g, f, data[f])
        if "target_value" in data and data["target_value"] is not None:
            g.target_value = _d(data["target_value"])
        self.db.add(g)
        await self.db.flush()
        await self.db.refresh(g)
        return await self._serialize_goal(g)

    async def delete_goal(self, actor: User, goal_id: uuid.UUID) -> None:
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can delete goals.")
        g = await self._get_goal(actor, goal_id)
        if actor.role == "Manager" and g.user_id not in await self._downline_ids(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not in your team.")
        g.is_deleted = True
        self.db.add(g)
        await self.db.flush()

    async def list_goals(self, actor: User, user_id=None, status_filter=None) -> list[dict]:
        q = select(PerformanceGoal).filter(PerformanceGoal.organization_id == actor.organization_id,
                                           PerformanceGoal.is_deleted == False)
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            q = q.filter(PerformanceGoal.user_id == user_id)
        else:
            scope = await self._scope_ids(actor)
            if scope is not None:
                q = q.filter(PerformanceGoal.user_id.in_(list(scope)))
        if status_filter:
            q = q.filter(PerformanceGoal.status == status_filter)
        rows = list((await self.db.execute(q.order_by(PerformanceGoal.end_date.desc()))).scalars().all())
        return [await self._serialize_goal(g) for g in rows]

    async def _goal_actual(self, org_id, g: PerformanceGoal, kpi: PerformanceKPI) -> float:
        metrics = await self._user_metrics(org_id, g.user_id, g.start_date, g.end_date)
        return float(metrics.get(kpi.metric, 0))

    # ================= Scorecard =================
    async def scorecard(self, actor: User, user_id: uuid.UUID, date_from: date, date_to: date) -> dict:
        await self._assert_can_view_user(actor, user_id)
        metrics = await self._user_metrics(actor.organization_id, user_id, date_from, date_to)
        kpis = list((await self.db.execute(select(PerformanceKPI).filter(
            PerformanceKPI.organization_id == actor.organization_id, PerformanceKPI.is_deleted == False,
            PerformanceKPI.status == "active"))).scalars().all())
        # active goals overlapping the window, keyed by kpi
        goals = list((await self.db.execute(select(PerformanceGoal).filter(
            PerformanceGoal.organization_id == actor.organization_id, PerformanceGoal.is_deleted == False,
            PerformanceGoal.user_id == user_id, PerformanceGoal.status == "active",
            PerformanceGoal.start_date <= date_to, PerformanceGoal.end_date >= date_from))).scalars().all())
        goal_by_kpi = {g.kpi_id: g for g in goals}
        rows = []
        weighted_sum = 0.0
        weight_total = 0.0
        for k in kpis:
            actual = float(metrics.get(k.metric, 0))
            g = goal_by_kpi.get(k.id)
            target = float(g.target_value) if g else None
            attainment = round(min(actual * 100 / target, 200), 1) if target else None
            rows.append({"kpi_id": str(k.id), "name": k.name, "metric": k.metric, "unit": k.unit,
                         "actual": actual, "target": target, "attainment": attainment,
                         "weight": float(k.weight)})
            if attainment is not None:
                weighted_sum += min(attainment, 100) * float(k.weight)
                weight_total += float(k.weight)
        composite = round(weighted_sum / weight_total, 1) if weight_total else None
        names = await self._names({user_id})
        return {"user_id": str(user_id), "user_name": names.get(user_id),
                "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "metrics": metrics, "kpis": rows, "composite_score": composite}

    # ================= Period performance (trends) =================
    async def period_performance(self, actor: User, user_id: uuid.UUID, granularity: str, count: int, metric=None) -> dict:
        await self._assert_can_view_user(actor, user_id)
        if granularity not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="granularity must be daily|weekly|monthly.")
        count = max(1, min(count, 26))
        today = date.today()
        buckets: list[tuple[date, date, str]] = []
        if granularity == "daily":
            for i in range(count - 1, -1, -1):
                d = today - timedelta(days=i)
                buckets.append((d, d, d.isoformat()))
        elif granularity == "weekly":
            monday = today - timedelta(days=today.weekday())
            for i in range(count - 1, -1, -1):
                s = monday - timedelta(days=7 * i)
                buckets.append((s, s + timedelta(days=6), f"W{s.isocalendar()[1]}"))
        else:  # monthly
            y, m = today.year, today.month
            months = []
            for _ in range(count):
                months.append((y, m))
                m -= 1
                if m == 0:
                    m = 12; y -= 1
            for (yy, mm) in reversed(months):
                s = date(yy, mm, 1)
                e = (date(yy + (mm == 12), (mm % 12) + 1, 1) - timedelta(days=1))
                buckets.append((s, e, s.strftime("%b %Y")))
        series = []
        for (s, e, label) in buckets:
            m = await self._user_metrics(actor.organization_id, user_id, s, e)
            row = {"label": label, "start": s.isoformat(), "end": e.isoformat()}
            row.update(m if not metric else {metric: m.get(metric, 0)})
            series.append(row)
        return {"user_id": str(user_id), "granularity": granularity, "series": series}

    # ================= Leaderboard =================
    async def leaderboard(self, actor: User, metric: str, date_from: date, date_to: date, limit: int = 20) -> list[dict]:
        if metric not in PERFORMANCE_METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {list(PERFORMANCE_METRICS)}")
        scope = await self._scope_ids(actor)
        uq = select(User).filter(User.organization_id == actor.organization_id, User.is_deleted == False,
                                 User.is_active == True, User.role != "SuperAdmin")
        if scope is not None:
            uq = uq.filter(User.id.in_(list(scope)))
        users = list((await self.db.execute(uq)).scalars().all())
        rows = []
        for u in users:
            m = await self._user_metrics(actor.organization_id, u.id, date_from, date_to)
            rows.append({"user_id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                         "value": float(m.get(metric, 0))})
        rows.sort(key=lambda x: -x["value"])
        rows = rows[:limit]
        for i, r in enumerate(rows, start=1):
            r["rank"] = i
        return rows

    # ================= Achievements =================
    async def evaluate_achievements(self, actor: User, as_of: date | None = None) -> dict:
        """Award achievements for goals whose window has data and whose target is
        met (attainment >= 100%). Idempotent per goal via a unique constraint."""
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a manager can evaluate achievements.")
        scope = await self._scope_ids(actor)
        gq = select(PerformanceGoal).filter(PerformanceGoal.organization_id == actor.organization_id,
                                            PerformanceGoal.is_deleted == False, PerformanceGoal.status == "active")
        if scope is not None:
            gq = gq.filter(PerformanceGoal.user_id.in_(list(scope)))
        goals = list((await self.db.execute(gq)).scalars().all())
        kpi_map = {k.id: k for k in (await self.db.execute(select(PerformanceKPI).filter(
            PerformanceKPI.organization_id == actor.organization_id))).scalars().all()}
        awarded = 0
        for g in goals:
            kpi = kpi_map.get(g.kpi_id)
            if not kpi:
                continue
            actual = await self._goal_actual(actor.organization_id, g, kpi)
            target = float(g.target_value or 0)
            if target <= 0 or actual < target:
                continue
            exists = (await self.db.execute(select(PerformanceAchievement.id).filter(
                PerformanceAchievement.goal_id == g.id, PerformanceAchievement.user_id == g.user_id))).scalar()
            if exists:
                continue
            attainment = round(actual * 100 / target, 1)
            badge = "Gold" if attainment >= 150 else "Silver" if attainment >= 120 else "Bronze"
            self.db.add(PerformanceAchievement(
                organization_id=actor.organization_id, user_id=g.user_id, goal_id=g.id, kpi_id=kpi.id,
                title=f"{kpi.name} target achieved", badge=badge,
                period_label=f"{g.start_date.isoformat()} → {g.end_date.isoformat()}",
                achieved_value=_d(actual), target_value=_d(target), attainment=_d(attainment), awarded_at=_now()))
            await self.db.flush()
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=g.user_id, category="performance",
                title=f"Achievement unlocked: {badge}",
                body=f"You hit your {kpi.name} target ({actual:g}/{target:g}).",
                link_url="/performance", priority="high", action_metadata={"goal_id": str(g.id)})
            # Workflow: goal achieved
            from app.services.workflow_service import WorkflowService
            ent = _GoalEvent(actor.organization_id, g.id, g.user_id, g.kpi_id, attainment)
            await WorkflowService(self.db).run("goal_achieved", ent, actor, entity_type="performance")
            awarded += 1
        return {"awarded": awarded}

    async def list_achievements(self, actor: User, user_id=None) -> list[dict]:
        q = select(PerformanceAchievement).filter(PerformanceAchievement.organization_id == actor.organization_id,
                                                  PerformanceAchievement.is_deleted == False)
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            q = q.filter(PerformanceAchievement.user_id == user_id)
        else:
            scope = await self._scope_ids(actor)
            if scope is not None:
                q = q.filter(PerformanceAchievement.user_id.in_(list(scope)))
        rows = list((await self.db.execute(q.order_by(PerformanceAchievement.awarded_at.desc()))).scalars().all())
        names = await self._names({r.user_id for r in rows})
        return [{"id": str(r.id), "user_id": str(r.user_id), "user_name": names.get(r.user_id),
                 "title": r.title, "badge": r.badge, "period_label": r.period_label,
                 "achieved_value": float(r.achieved_value), "target_value": float(r.target_value),
                 "attainment": float(r.attainment), "awarded_at": r.awarded_at.isoformat()} for r in rows]

    # ================= Dashboard & reports =================
    async def dashboard(self, actor: User) -> dict:
        today = date.today()
        month_start = today.replace(day=1)
        me = await self._user_metrics(actor.organization_id, actor.id, month_start, today)
        my_score = await self.scorecard(actor, actor.id, month_start, today)
        my_open_goals = (await self.db.execute(select(func.count(PerformanceGoal.id)).filter(
            PerformanceGoal.organization_id == actor.organization_id, PerformanceGoal.user_id == actor.id,
            PerformanceGoal.is_deleted == False, PerformanceGoal.status == "active",
            PerformanceGoal.end_date >= today))).scalar() or 0
        my_achievements = (await self.db.execute(select(func.count(PerformanceAchievement.id)).filter(
            PerformanceAchievement.organization_id == actor.organization_id,
            PerformanceAchievement.user_id == actor.id, PerformanceAchievement.is_deleted == False))).scalar() or 0
        # a compact conversion-rate leaderboard snapshot
        top = await self.leaderboard(actor, "sales_revenue", month_start, today, limit=5)
        return {"my_metrics": me, "my_composite_score": my_score["composite_score"],
                "my_open_goals": my_open_goals, "my_achievements": my_achievements,
                "top_sales": top}

    async def report(self, actor: User, date_from: date, date_to: date, user_id=None) -> dict:
        if user_id:
            await self._assert_can_view_user(actor, user_id)
            scope = {user_id}
        else:
            scope = await self._scope_ids(actor)
        uq = select(User).filter(User.organization_id == actor.organization_id, User.is_deleted == False,
                                 User.role != "SuperAdmin")
        if scope is not None:
            uq = uq.filter(User.id.in_(list(scope)))
        users = list((await self.db.execute(uq)).scalars().all())
        rows = []
        for u in users:
            m = await self._user_metrics(actor.organization_id, u.id, date_from, date_to)
            rows.append({"user_id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                         "role": u.role, **m})
        rows.sort(key=lambda x: -x["sales_revenue"])
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "rows": rows}

    # ---------- helpers ----------
    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    def _serialize_kpi(self, k: PerformanceKPI) -> dict:
        return {"id": str(k.id), "name": k.name, "code": k.code, "metric": k.metric,
                "description": k.description, "unit": k.unit, "weight": float(k.weight),
                "higher_is_better": k.higher_is_better, "status": k.status, "color": k.color,
                "created_at": k.created_at}

    async def _serialize_goal(self, g: PerformanceGoal) -> dict:
        kpi = (await self.db.execute(select(PerformanceKPI).filter(PerformanceKPI.id == g.kpi_id))).scalars().first()
        names = await self._names({g.user_id})
        actual = await self._goal_actual(g.organization_id, g, kpi) if kpi else 0.0
        target = float(g.target_value or 0)
        return {"id": str(g.id), "user_id": str(g.user_id), "user_name": names.get(g.user_id),
                "kpi_id": str(g.kpi_id), "kpi_name": kpi.name if kpi else None,
                "metric": kpi.metric if kpi else None, "unit": kpi.unit if kpi else None,
                "period": g.period, "target_value": target, "actual": actual,
                "attainment": round(actual * 100 / target, 1) if target else 0.0,
                "start_date": g.start_date.isoformat(), "end_date": g.end_date.isoformat(),
                "status": g.status, "created_at": g.created_at}


class _GoalEvent:
    """Lightweight (non-ORM) entity for the workflow engine's goal_achieved rules."""
    def __init__(self, organization_id, goal_id, user_id, kpi_id, attainment):
        self.organization_id = organization_id
        self.id = goal_id
        self.user_id = user_id
        self.kpi_id = kpi_id
        self.attainment = attainment

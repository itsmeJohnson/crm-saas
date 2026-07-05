"""Target Management service — a unifying layer over the three existing target
stores, adding nothing to the schema:

* Individual targets  → PerformanceGoal   (performance module)
* Team targets        → TeamTarget        (team module)
* Department targets  → DepartmentTarget   (department module)

It reuses each module's metric rollup to compute live progress (actual vs
target, attainment, on-track pace), and presents a single cross-scope list,
dashboard and report. Creating a target here delegates to the owning service,
so validation, notifications and the goal_achieved workflow all still fire.
"""
from __future__ import annotations
import uuid
import calendar as _cal
from datetime import date, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.performance import PerformanceGoal, PerformanceKPI
from app.models.team import Team, TeamTarget
from app.models.department import Department, DepartmentTarget
from app.services.performance_service import PerformanceService
from app.services.team_service import TeamService
from app.services.department_service import DepartmentService

SCOPES = ("individual", "team", "department")
PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")


def _period_window(period: str, today: date | None = None) -> tuple[date, date]:
    """Fallback window for a target with no explicit dates: the current period."""
    today = today or date.today()
    if period == "daily":
        return today, today
    if period == "weekly":
        s = today - timedelta(days=today.weekday())
        return s, s + timedelta(days=6)
    if period == "quarterly":
        q = (today.month - 1) // 3
        s = date(today.year, q * 3 + 1, 1)
        em = q * 3 + 3
        e = date(today.year, em, _cal.monthrange(today.year, em)[1])
        return s, e
    if period == "yearly":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    # monthly (default)
    s = today.replace(day=1)
    return s, date(today.year, today.month, _cal.monthrange(today.year, today.month)[1])


def _progress(actual: float, target: float, start: date, end: date, today: date | None = None) -> dict:
    today = today or date.today()
    attainment = round(actual * 100 / target, 1) if target else 0.0
    achieved = attainment >= 100
    # expected pace: fraction of the window elapsed
    span = max(1, (end - start).days + 1)
    elapsed = min(span, max(0, (today - start).days + 1))
    expected = target * (elapsed / span) if target else 0
    if today > end:
        status_label = "achieved" if achieved else "missed"
    elif achieved:
        status_label = "achieved"
    elif actual >= expected * 0.85:
        status_label = "on_track"
    else:
        status_label = "at_risk"
    return {"actual": round(actual, 2), "attainment": attainment, "achieved": achieved,
            "status_label": status_label}


class TargetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.perf = PerformanceService(db)
        self.teams = TeamService(db)
        self.depts = DepartmentService(db)

    def _is_manager(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ================= Aggregated list =================
    async def list_targets(self, actor: User, scope: str | None = None, period: str | None = None,
                           status_filter: str = "active") -> list[dict]:
        rows: list[dict] = []
        if scope in (None, "individual"):
            rows += await self._individual_rows(actor, period, status_filter)
        if scope in (None, "team"):
            rows += await self._team_rows(actor, period, status_filter)
        if scope in (None, "department"):
            rows += await self._department_rows(actor, period, status_filter)
        rows.sort(key=lambda r: (r["scope"], -r["attainment"]))
        return rows

    async def _individual_rows(self, actor: User, period, status_filter) -> list[dict]:
        scope_ids = await self.perf._scope_ids(actor)
        q = select(PerformanceGoal).filter(PerformanceGoal.organization_id == actor.organization_id,
                                           PerformanceGoal.is_deleted == False)
        if status_filter:
            q = q.filter(PerformanceGoal.status == status_filter)
        if period:
            q = q.filter(PerformanceGoal.period == period)
        if scope_ids is not None:
            q = q.filter(PerformanceGoal.user_id.in_(list(scope_ids)))
        goals = list((await self.db.execute(q)).scalars().all())
        if not goals:
            return []
        kpis = {k.id: k for k in (await self.db.execute(select(PerformanceKPI).filter(
            PerformanceKPI.organization_id == actor.organization_id))).scalars().all()}
        names = await self.perf._names({g.user_id for g in goals})
        out = []
        for g in goals:
            kpi = kpis.get(g.kpi_id)
            metric = kpi.metric if kpi else None
            m = await self.perf._user_metrics(actor.organization_id, g.user_id, g.start_date, g.end_date)
            actual = float(m.get(metric, 0)) if metric else 0.0
            out.append(self._row("individual", str(g.id), names.get(g.user_id), kpi.name if kpi else "—",
                                  metric, g.period, float(g.target_value), actual, g.start_date, g.end_date,
                                  g.status, kpi.unit if kpi else "count"))
        return out

    async def _team_rows(self, actor: User, period, status_filter) -> list[dict]:
        visible = await self.teams._visible_team_ids(actor)
        tq = select(Team).filter(Team.organization_id == actor.organization_id, Team.is_deleted == False)
        if visible is not None:
            if not visible:
                return []
            tq = tq.filter(Team.id.in_(list(visible)))
        teams = {t.id: t for t in (await self.db.execute(tq)).scalars().all()}
        if not teams:
            return []
        gq = select(TeamTarget).filter(TeamTarget.organization_id == actor.organization_id,
                                       TeamTarget.is_deleted == False, TeamTarget.team_id.in_(list(teams.keys())))
        if period:
            gq = gq.filter(TeamTarget.period == period)
        targets = list((await self.db.execute(gq)).scalars().all())
        out = []
        for t in targets:
            team = teams.get(t.team_id)
            start = t.start_date or _period_window(t.period)[0]
            end = t.end_date or _period_window(t.period)[1]
            member_ids = await self.teams._member_ids(t.team_id)
            m = await self.depts._metrics_for_members(actor.organization_id, member_ids, start, end)
            actual = float(m.get(t.metric, 0))
            out.append(self._row("team", str(t.id), team.name if team else "—", t.name, t.metric, t.period,
                                  float(t.target_value), actual, start, end, "active",
                                  "currency" if t.metric == "revenue" else "count"))
        return out

    async def _department_rows(self, actor: User, period, status_filter) -> list[dict]:
        # departments are broadly visible; managers/admins see all, others their own dept
        dq = select(Department).filter(Department.organization_id == actor.organization_id,
                                       Department.is_deleted == False)
        if not self._is_manager(actor):
            if not actor.department_id:
                return []
            dq = dq.filter(Department.id == actor.department_id)
        depts = {d.id: d for d in (await self.db.execute(dq)).scalars().all()}
        if not depts:
            return []
        gq = select(DepartmentTarget).filter(DepartmentTarget.organization_id == actor.organization_id,
                                             DepartmentTarget.is_deleted == False,
                                             DepartmentTarget.department_id.in_(list(depts.keys())))
        if period:
            gq = gq.filter(DepartmentTarget.period == period)
        targets = list((await self.db.execute(gq)).scalars().all())
        out = []
        for t in targets:
            d = depts.get(t.department_id)
            start = t.start_date or _period_window(t.period)[0]
            end = t.end_date or _period_window(t.period)[1]
            member_ids = await self.depts._member_ids(actor.organization_id, t.department_id)
            m = await self.depts._metrics_for_members(actor.organization_id, member_ids, start, end)
            actual = float(m.get(t.metric, 0))
            out.append(self._row("department", str(t.id), d.name if d else "—", t.name, t.metric, t.period,
                                  float(t.target_value), actual, start, end, "active",
                                  "currency" if t.metric == "revenue" else "count"))
        return out

    @staticmethod
    def _row(scope, tid, scope_name, name, metric, period, target, actual, start, end, status_val, unit) -> dict:
        p = _progress(actual, target, start, end)
        return {"id": tid, "scope": scope, "scope_name": scope_name, "name": name, "metric": metric,
                "unit": unit, "period": period, "target_value": target, "start_date": start.isoformat(),
                "end_date": end.isoformat(), "status": status_val, **p}

    # ================= Dashboard & report =================
    async def dashboard(self, actor: User) -> dict:
        rows = await self.list_targets(actor)
        total = len(rows)
        achieved = sum(1 for r in rows if r["achieved"])
        on_track = sum(1 for r in rows if r["status_label"] == "on_track")
        at_risk = sum(1 for r in rows if r["status_label"] == "at_risk")
        missed = sum(1 for r in rows if r["status_label"] == "missed")
        by_scope: dict[str, int] = {}
        by_period: dict[str, int] = {}
        for r in rows:
            by_scope[r["scope"]] = by_scope.get(r["scope"], 0) + 1
            by_period[r["period"]] = by_period.get(r["period"], 0) + 1
        avg_attainment = round(sum(r["attainment"] for r in rows) / total, 1) if total else 0.0
        return {"total": total, "achieved": achieved, "on_track": on_track, "at_risk": at_risk,
                "missed": missed, "avg_attainment": avg_attainment, "by_scope": by_scope,
                "by_period": by_period,
                "at_risk_targets": [r for r in rows if r["status_label"] == "at_risk"][:5]}

    async def report(self, actor: User, scope: str | None = None, period: str | None = None) -> dict:
        rows = await self.list_targets(actor, scope=scope, period=period)
        return {"rows": rows, "count": len(rows)}

    # ================= Delegating create =================
    async def create_target(self, actor: User, data: dict) -> dict:
        """Route creation to the owning module so its validation, notifications
        and workflow fire. Returns a unified row for the created target."""
        scope = data.get("scope")
        if scope not in SCOPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"scope must be one of {list(SCOPES)}")
        period = data.get("period", "monthly")
        if period not in PERIODS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"period must be one of {list(PERIODS)}")
        if scope == "individual":
            if not data.get("user_id") or not data.get("kpi_id"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="individual targets need user_id and kpi_id.")
            start, end = data.get("start_date"), data.get("end_date")
            if not start or not end:
                start, end = _period_window(period)
            await self.perf.create_goal(actor, {"user_id": data["user_id"], "kpi_id": data["kpi_id"],
                                                "period": period, "target_value": data["target_value"],
                                                "start_date": start, "end_date": end})
        elif scope == "team":
            if not data.get("team_id") or not data.get("metric") or not data.get("name"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="team targets need team_id, name and metric.")
            await self.teams.create_target(actor, data["team_id"], {
                "name": data["name"], "metric": data["metric"], "target_value": data["target_value"],
                "period": period, "start_date": data.get("start_date"), "end_date": data.get("end_date")})
        else:  # department
            if not data.get("department_id") or not data.get("metric") or not data.get("name"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="department targets need department_id, name and metric.")
            await self.depts.create_target(actor, data["department_id"], {
                "name": data["name"], "metric": data["metric"], "target_value": data["target_value"],
                "period": period, "start_date": data.get("start_date"), "end_date": data.get("end_date")})
        return {"scope": scope, "created": True}

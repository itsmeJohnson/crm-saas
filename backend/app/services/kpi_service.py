"""KPI Engine.

A registry of user-configured KPIs across every domain (sales, pipeline,
financial, communication, workflow, automation, employee, department, team, plus
fully-custom manual KPIs) with targets and warning/critical thresholds. The
engine evaluates each KPI against a live metric snapshot (composed from the
existing analytics services — nothing is recomputed here), raises/resolves alerts
on threshold breaches, notifies, and powers a KPI dashboard and reports.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.kpi import KPIDefinition, KPIAlert
from app.services.notification_service import NotificationService

CATEGORIES = ("custom", "sales", "pipeline", "financial", "communication",
              "workflow", "automation", "employee", "department", "team")
COMPARISONS = ("higher_better", "lower_better")
UNITS = ("count", "percent", "currency", "seconds")

# catalog metric key -> metadata. `manual` (category custom) reads the KPI's
# manual_value; every other key is filled by _snapshot from an analytics service.
METRIC_CATALOG: dict[str, dict] = {
    "manual":               {"label": "Manual value",            "category": "custom",        "unit": "count",    "comparison": "higher_better"},
    # sales
    "sales_conversion_rate": {"label": "Lead conversion rate",   "category": "sales",         "unit": "percent",  "comparison": "higher_better"},
    "sales_win_rate":       {"label": "Win rate",                "category": "sales",         "unit": "percent",  "comparison": "higher_better"},
    "avg_deal_size":        {"label": "Average deal size",       "category": "sales",         "unit": "currency", "comparison": "higher_better"},
    "sales_revenue":        {"label": "Sales revenue",           "category": "sales",         "unit": "currency", "comparison": "higher_better"},
    "sales_velocity":       {"label": "Sales velocity",          "category": "sales",         "unit": "currency", "comparison": "higher_better"},
    # pipeline
    "pipeline_value":       {"label": "Open pipeline value",     "category": "pipeline",      "unit": "currency", "comparison": "higher_better"},
    "open_deals":           {"label": "Open deals",              "category": "pipeline",      "unit": "count",    "comparison": "higher_better"},
    # financial
    "mrr":                  {"label": "MRR",                     "category": "financial",     "unit": "currency", "comparison": "higher_better"},
    "arr":                  {"label": "ARR",                     "category": "financial",     "unit": "currency", "comparison": "higher_better"},
    "gross_profit":         {"label": "Gross profit",           "category": "financial",     "unit": "currency", "comparison": "higher_better"},
    "profit_margin":        {"label": "Profit margin",          "category": "financial",     "unit": "percent",  "comparison": "higher_better"},
    "collection_rate":      {"label": "Collection rate",        "category": "financial",     "unit": "percent",  "comparison": "higher_better"},
    "outstanding_ar":       {"label": "Outstanding AR",         "category": "financial",     "unit": "currency", "comparison": "lower_better"},
    "churn_rate":           {"label": "Churn rate",             "category": "financial",     "unit": "percent",  "comparison": "lower_better"},
    # communication
    "comm_delivery_rate":   {"label": "Message delivery rate",  "category": "communication", "unit": "percent",  "comparison": "higher_better"},
    "call_quality_score":   {"label": "Call quality score",     "category": "communication", "unit": "percent",  "comparison": "higher_better"},
    "avg_response_seconds": {"label": "Avg response time",      "category": "communication", "unit": "seconds",  "comparison": "lower_better"},
    "missed_calls":         {"label": "Missed calls",           "category": "communication", "unit": "count",    "comparison": "lower_better"},
    # workflow
    "workflow_success_rate": {"label": "Workflow success rate", "category": "workflow",      "unit": "percent",  "comparison": "higher_better"},
    "workflow_failures":    {"label": "Workflow failures",      "category": "workflow",      "unit": "count",    "comparison": "lower_better"},
    # automation
    "sla_compliance":       {"label": "SLA compliance",         "category": "automation",    "unit": "percent",  "comparison": "higher_better"},
    "open_sla_breaches":    {"label": "Open SLA breaches",      "category": "automation",    "unit": "count",    "comparison": "lower_better"},
    "escalations":          {"label": "Escalations",            "category": "automation",    "unit": "count",    "comparison": "lower_better"},
    # employee
    "avg_productivity":     {"label": "Avg productivity",       "category": "employee",      "unit": "count",    "comparison": "higher_better"},
    "avg_attendance":       {"label": "Avg attendance",         "category": "employee",      "unit": "percent",  "comparison": "higher_better"},
    "headcount":            {"label": "Headcount",              "category": "employee",      "unit": "count",    "comparison": "higher_better"},
    "avg_training_score":   {"label": "Avg training score",     "category": "employee",      "unit": "percent",  "comparison": "higher_better"},
    # department / team
    "department_count":     {"label": "Active departments",     "category": "department",    "unit": "count",    "comparison": "higher_better"},
    "team_count":           {"label": "Active teams",           "category": "team",          "unit": "count",    "comparison": "higher_better"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class KPIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="The KPI engine is available to managers and admins only.")

    def catalog(self) -> dict:
        return {"categories": list(CATEGORIES), "comparisons": list(COMPARISONS), "units": list(UNITS),
                "metrics": [{"key": k, **v} for k, v in METRIC_CATALOG.items()]}

    # ================= metric snapshot (reuses analytics services) =================
    async def _snapshot(self, actor: User, date_from: date | None = None) -> dict:
        org = actor.organization_id
        snap: dict = {}
        try:
            from app.services.sales_analytics_service import SalesAnalyticsService
            s = await SalesAnalyticsService(self.db).overview(actor, date_from, None)
            snap.update({"sales_conversion_rate": s.get("conversion_rate"), "sales_win_rate": s.get("win_rate"),
                         "avg_deal_size": s.get("avg_deal_size"), "sales_revenue": s.get("revenue"),
                         "sales_velocity": s.get("sales_velocity"), "pipeline_value": s.get("pipeline_value"),
                         "open_deals": s.get("open")})
        except Exception:
            pass
        try:
            from app.services.financial_analytics_service import FinancialAnalyticsService
            fa = FinancialAnalyticsService(self.db)
            fo = await fa.overview(actor, date_from, None)
            fr = await fa.recurring(actor, date_from, None)
            fc = await fa.collections(actor, date_from, None)
            snap.update({"mrr": fr.get("mrr"), "arr": fr.get("arr"), "gross_profit": fo.get("gross_profit"),
                         "profit_margin": fo.get("profit_margin"), "collection_rate": fc.get("collection_rate"),
                         "outstanding_ar": fo.get("outstanding"), "churn_rate": fr.get("churn_rate")})
        except Exception:
            pass
        try:
            from app.services.communication_analytics_service import CommunicationAnalyticsService
            ca = CommunicationAnalyticsService(self.db)
            co = await ca.overview(actor)
            cq = await ca.call_quality(actor)
            rt = await ca.response_time(actor)
            ms = await ca.missed(actor)
            snap.update({"comm_delivery_rate": co.get("delivery_rate"), "call_quality_score": cq.get("quality_score"),
                         "avg_response_seconds": rt.get("avg_response_seconds"), "missed_calls": ms.get("missed_calls")})
        except Exception:
            pass
        try:
            from app.services.automation_analytics_service import AutomationAnalyticsService
            ao = await AutomationAnalyticsService(self.db).overview(actor, date_from, None)
            wf, sla, esc = ao.get("workflow", {}), ao.get("sla", {}), ao.get("escalation", {})
            snap.update({"workflow_success_rate": wf.get("success_rate"), "workflow_failures": wf.get("failed"),
                         "sla_compliance": sla.get("compliance_rate"), "open_sla_breaches": sla.get("open_breaches"),
                         "escalations": esc.get("total")})
        except Exception:
            pass
        try:
            from app.services.employee_analytics_service import EmployeeAnalyticsService
            ed = await EmployeeAnalyticsService(self.db).dashboard(actor)
            snap.update({"avg_productivity": ed.get("avg_productivity"), "avg_attendance": ed.get("avg_attendance"),
                         "headcount": ed.get("headcount"), "avg_training_score": ed.get("avg_training_score")})
        except Exception:
            pass
        try:
            from app.models.department import Department
            from app.models.team import Team
            snap["department_count"] = (await self.db.execute(select(func.count(Department.id)).filter(
                Department.organization_id == org, Department.is_deleted == False))).scalar() or 0
            snap["team_count"] = (await self.db.execute(select(func.count(Team.id)).filter(
                Team.organization_id == org, Team.is_deleted == False))).scalar() or 0
        except Exception:
            pass
        return snap

    # ================= evaluation =================
    def _status(self, kpi: KPIDefinition, value) -> str:
        if value is None:
            return "unknown"
        w = _num(kpi.warning_value)
        c = _num(kpi.critical_value)
        if kpi.comparison == "lower_better":
            if c is not None and value >= c:
                return "critical"
            if w is not None and value >= w:
                return "warning"
            return "on_track"
        if c is not None and value <= c:
            return "critical"
        if w is not None and value <= w:
            return "warning"
        return "on_track"

    def _attainment(self, kpi: KPIDefinition, value) -> float | None:
        if value is None:
            return None
        target = _num(kpi.target_value) or 0
        if target == 0:
            return None
        if kpi.comparison == "lower_better":
            return round(min(200.0, target * 100 / value), 1) if value else 200.0
        return round(value * 100 / target, 1)

    def _kpi_value(self, kpi: KPIDefinition, snapshot: dict):
        if kpi.metric == "manual":
            return _num(kpi.manual_value)
        return _num(snapshot.get(kpi.metric))

    def _evaluate_one(self, kpi: KPIDefinition, snapshot: dict) -> dict:
        value = self._kpi_value(kpi, snapshot)
        st = self._status(kpi, value)
        return {**self._serialize(kpi), "value": value, "status": st, "attainment": self._attainment(kpi, value)}

    # ================= CRUD =================
    async def _get(self, actor: User, kpi_id: uuid.UUID) -> KPIDefinition:
        k = (await self.db.execute(select(KPIDefinition).filter(
            KPIDefinition.id == kpi_id, KPIDefinition.organization_id == actor.organization_id,
            KPIDefinition.is_deleted == False))).scalars().first()
        if not k:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
        return k

    def _validate(self, data: dict):
        if data.get("category") and data["category"] not in CATEGORIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"category must be one of {list(CATEGORIES)}")
        metric = data.get("metric")
        if metric and metric not in METRIC_CATALOG:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown metric '{metric}'.")
        if data.get("comparison") and data["comparison"] not in COMPARISONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"comparison must be one of {list(COMPARISONS)}")

    async def list_kpis(self, actor: User, category=None, active_only=False) -> list[dict]:
        q = select(KPIDefinition).filter(KPIDefinition.organization_id == actor.organization_id,
                                         KPIDefinition.is_deleted == False)
        if category:
            q = q.filter(KPIDefinition.category == category)
        if active_only:
            q = q.filter(KPIDefinition.is_active == True)
        rows = (await self.db.execute(q.order_by(KPIDefinition.category.asc(), KPIDefinition.created_at.desc()))).scalars().all()
        return [self._serialize(k) for k in rows]

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        metric = data.get("metric") or "manual"
        meta = METRIC_CATALOG.get(metric, {})
        k = KPIDefinition(
            organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
            category=data.get("category") or meta.get("category", "custom"), metric=metric,
            unit=data.get("unit") or meta.get("unit", "count"),
            comparison=data.get("comparison") or meta.get("comparison", "higher_better"),
            target_value=data.get("target_value") or 0, warning_value=data.get("warning_value"),
            critical_value=data.get("critical_value"), manual_value=data.get("manual_value"),
            window_days=int(data.get("window_days") or 30), is_active=bool(data.get("is_active", True)),
            notify=bool(data.get("notify", True)), notify_roles=data.get("notify_roles"), created_by=actor.id)
        self.db.add(k)
        await self.db.flush()
        await self.db.refresh(k)
        return self._serialize(k)

    async def update(self, actor: User, kpi_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        k = await self._get(actor, kpi_id)
        for f in ("name", "description", "category", "metric", "unit", "comparison", "target_value",
                  "warning_value", "critical_value", "manual_value", "window_days", "is_active", "notify", "notify_roles"):
            if f in data and data[f] is not None:
                setattr(k, f, data[f])
        self.db.add(k)
        await self.db.flush()
        await self.db.refresh(k)
        return self._serialize(k)

    async def delete(self, actor: User, kpi_id: uuid.UUID) -> None:
        self._require_manager(actor)
        k = await self._get(actor, kpi_id)
        k.is_deleted = True
        self.db.add(k)
        await self.db.flush()

    async def evaluate(self, actor: User, kpi_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        k = await self._get(actor, kpi_id)
        snap = await self._snapshot(actor, date.today() - timedelta(days=k.window_days))
        return self._evaluate_one(k, snap)

    # ================= dashboard / report =================
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        kpis = (await self.db.execute(select(KPIDefinition).filter(
            KPIDefinition.organization_id == actor.organization_id, KPIDefinition.is_deleted == False,
            KPIDefinition.is_active == True))).scalars().all()
        snap = await self._snapshot(actor)
        evals = [self._evaluate_one(k, snap) for k in kpis]
        summary = {"total": len(evals), "on_track": 0, "warning": 0, "critical": 0, "unknown": 0}
        by_category: dict = {}
        for e in evals:
            summary[e["status"]] = summary.get(e["status"], 0) + 1
            by_category.setdefault(e["category"], []).append(e)
        open_alerts = (await self.db.execute(select(func.count(KPIAlert.id)).filter(
            KPIAlert.organization_id == actor.organization_id, KPIAlert.is_deleted == False,
            KPIAlert.resolved == False))).scalar() or 0
        return {"summary": summary, "open_alerts": open_alerts, "kpis": evals,
                "by_category": {k: v for k, v in by_category.items()}}

    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        d = await self.dashboard(actor)
        cat_rows = []
        for cat, items in d["by_category"].items():
            cat_rows.append({"category": cat, "count": len(items),
                             "on_track": sum(1 for i in items if i["status"] == "on_track"),
                             "warning": sum(1 for i in items if i["status"] == "warning"),
                             "critical": sum(1 for i in items if i["status"] == "critical")})
        cat_rows.sort(key=lambda r: -r["count"])
        return {"summary": d["summary"], "open_alerts": d["open_alerts"], "by_category": cat_rows}

    # ================= alerts + evaluation cycle =================
    async def list_alerts(self, actor: User, resolved: bool | None = None, limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        q = select(KPIAlert).filter(KPIAlert.organization_id == actor.organization_id, KPIAlert.is_deleted == False)
        if resolved is not None:
            q = q.filter(KPIAlert.resolved == resolved)
        rows = (await self.db.execute(q.order_by(KPIAlert.created_at.desc()).limit(min(limit, 300)))).scalars().all()
        names = {k.id: k.name for k in (await self.db.execute(select(KPIDefinition).filter(
            KPIDefinition.organization_id == actor.organization_id))).scalars().all()}
        return [{"id": str(a.id), "kpi_id": str(a.kpi_id), "kpi_name": names.get(a.kpi_id, "—"),
                 "status": a.status, "value": _num(a.value), "target_value": _num(a.target_value),
                 "message": a.message, "resolved": a.resolved,
                 "created_at": a.created_at.isoformat() if a.created_at else None,
                 "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None} for a in rows]

    async def resolve_alert(self, actor: User, alert_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        a = (await self.db.execute(select(KPIAlert).filter(
            KPIAlert.id == alert_id, KPIAlert.organization_id == actor.organization_id,
            KPIAlert.is_deleted == False))).scalars().first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        a.resolved = True
        a.resolved_at = _now()
        self.db.add(a)
        await self.db.flush()
        return {"id": str(a.id), "resolved": True}

    async def evaluate_all(self, org_id: uuid.UUID, actor: User | None = None) -> dict:
        """Evaluate every active KPI, raise/resolve alerts and notify. Used by the
        cron (actor=None → resolves an org admin) and the on-demand endpoint."""
        if actor is None:
            actor = (await self.db.execute(select(User).filter(
                User.organization_id == org_id, User.is_deleted == False,
                User.role.in_(["OrgAdmin", "SuperAdmin"])).limit(1))).scalars().first()
            if not actor:
                return {"evaluated": 0, "raised": 0, "resolved": 0}
        kpis = (await self.db.execute(select(KPIDefinition).filter(
            KPIDefinition.organization_id == org_id, KPIDefinition.is_deleted == False,
            KPIDefinition.is_active == True))).scalars().all()
        snap = await self._snapshot(actor)
        raised = resolved = 0
        for k in kpis:
            value = self._kpi_value(k, snap)
            st = self._status(k, value)
            open_alert = (await self.db.execute(select(KPIAlert).filter(
                KPIAlert.kpi_id == k.id, KPIAlert.resolved == False, KPIAlert.is_deleted == False))).scalars().first()
            if st in ("warning", "critical"):
                if open_alert is None:
                    alert = KPIAlert(organization_id=org_id, kpi_id=k.id, status=st, value=value or 0,
                                     target_value=k.target_value,
                                     message=f'"{k.name}" is {st}: {round(value, 2) if value is not None else "?"} vs target {float(k.target_value)}')
                    self.db.add(alert)
                    await self.db.flush()
                    raised += 1
                    if k.notify:
                        await self._notify(org_id, k, alert)
                        alert.notified = True
                        self.db.add(alert)
                elif open_alert.status != st:
                    open_alert.status = st
                    open_alert.value = value or 0
                    self.db.add(open_alert)
                    if st == "critical" and k.notify:
                        await self._notify(org_id, k, open_alert)
            elif open_alert is not None:  # recovered
                open_alert.resolved = True
                open_alert.resolved_at = _now()
                self.db.add(open_alert)
                resolved += 1
        await self.db.flush()
        return {"evaluated": len(kpis), "raised": raised, "resolved": resolved}

    async def evaluate_all_for(self, actor: User) -> dict:
        self._require_manager(actor)
        return await self.evaluate_all(actor.organization_id, actor)

    async def _notify(self, org_id, kpi: KPIDefinition, alert: KPIAlert):
        roles = kpi.notify_roles or ["OrgAdmin"]
        recipients = (await self.db.execute(select(User.id).filter(
            User.organization_id == org_id, User.is_deleted == False, User.role.in_(roles)))).scalars().all()
        for uid in recipients:
            try:
                await self.notifier.create_notification(
                    organization_id=org_id, user_id=uid, category="kpi",
                    title=f"KPI {alert.status}: {kpi.name}", body=alert.message or "",
                    link_url="/kpi", priority="high" if alert.status == "critical" else "normal",
                    action_metadata={"kpi_id": str(kpi.id), "alert_id": str(alert.id)})
            except Exception:
                pass

    # ---------- serialize ----------
    def _serialize(self, k: KPIDefinition) -> dict:
        return {"id": str(k.id), "name": k.name, "description": k.description, "category": k.category,
                "metric": k.metric, "unit": k.unit, "comparison": k.comparison,
                "target_value": _num(k.target_value), "warning_value": _num(k.warning_value),
                "critical_value": _num(k.critical_value), "manual_value": _num(k.manual_value),
                "window_days": k.window_days, "is_active": k.is_active, "notify": k.notify,
                "notify_roles": k.notify_roles or ["OrgAdmin"],
                "created_at": k.created_at.isoformat() if k.created_at else None}

"""Executive Dashboard — a role/persona-aware executive cockpit.

This is a COMPOSITION layer: it does not reimplement any analytics. Each widget
delegates to the module that already owns that data (org analytics, communication
analytics, automation analytics, customer/AR, campaigns, targets, dashboard
summary) and reshapes it into a compact executive block. It adds the four
genuinely-missing executive widgets — Forecast, Cash Flow, Customer Satisfaction
and AI Insights — plus saved views / widget configuration.

Personas curate which widgets a viewer sees (ceo/sales/finance/hr/support/
operations); scope selects the structural lens (organization/branch/department/
team). Every block is best-effort: a failing subsystem yields an {error} block
rather than breaking the whole dashboard.
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
from app.models.lead import Lead
from app.models.support_ticket import SupportTicket
from app.models.dashboard_view import DashboardView

PERSONAS = ("ceo", "sales", "finance", "hr", "support", "operations")
SCOPES = ("organization", "branch", "department", "team")

# widget id → metadata. `drill` is the frontend route the card links to.
WIDGET_CATALOG: dict[str, dict] = {
    "revenue":                {"label": "Revenue",               "category": "sales",    "drill": "/org-analytics"},
    "pipeline":               {"label": "Pipeline",              "category": "sales",    "drill": "/leads"},
    "conversion_rate":        {"label": "Conversion Rate",       "category": "sales",    "drill": "/org-analytics"},
    "collections":            {"label": "Collections",           "category": "finance",  "drill": "/customers"},
    "lead_sources":           {"label": "Lead Sources",          "category": "sales",    "drill": "/leads"},
    "communication_summary":  {"label": "Communication Summary", "category": "support",  "drill": "/communications"},
    "call_statistics":        {"label": "Call Statistics",       "category": "support",  "drill": "/communications"},
    "agent_productivity":     {"label": "Agent Productivity",    "category": "sales",    "drill": "/org-analytics"},
    "department_performance": {"label": "Department Performance", "category": "ops",     "drill": "/departments"},
    "target_achievement":     {"label": "Target Achievement",    "category": "sales",    "drill": "/targets"},
    "forecast":               {"label": "Forecast",              "category": "finance",  "drill": "/org-analytics"},
    "cash_flow":              {"label": "Cash Flow",             "category": "finance",  "drill": "/customers"},
    "attendance":             {"label": "Attendance",            "category": "hr",       "drill": "/attendance"},
    "leave":                  {"label": "Leave",                 "category": "hr",       "drill": "/leaves"},
    "workflow_status":        {"label": "Workflow Status",       "category": "ops",      "drill": "/automation-analytics"},
    "automation_health":      {"label": "Automation Health",     "category": "ops",      "drill": "/automation-analytics"},
    "sla_compliance":         {"label": "SLA Compliance",        "category": "support",  "drill": "/sla"},
    "escalations":            {"label": "Escalations",           "category": "support",  "drill": "/escalation"},
    "campaign_performance":   {"label": "Campaign Performance",  "category": "sales",    "drill": "/campaigns"},
    "customer_satisfaction":  {"label": "Customer Satisfaction", "category": "support",  "drill": "/support"},
    "ai_insights":            {"label": "AI Insights",           "category": "exec",     "drill": None},
}

# default widget bundle per persona (ordered)
PERSONA_LAYOUTS: dict[str, list[str]] = {
    "ceo": ["revenue", "pipeline", "conversion_rate", "collections", "forecast", "cash_flow",
            "target_achievement", "department_performance", "sla_compliance", "customer_satisfaction", "ai_insights"],
    "sales": ["revenue", "pipeline", "conversion_rate", "lead_sources", "forecast",
              "target_achievement", "agent_productivity", "campaign_performance"],
    "finance": ["revenue", "collections", "cash_flow", "forecast", "target_achievement"],
    "hr": ["attendance", "leave", "department_performance", "target_achievement"],
    "support": ["sla_compliance", "escalations", "customer_satisfaction", "communication_summary", "call_statistics"],
    "operations": ["workflow_status", "automation_health", "sla_compliance", "escalations",
                   "department_performance", "campaign_performance"],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class ExecutiveDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / window ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="The executive dashboard is available to managers and admins only.")

    def _window(self, date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
        today = date.today()
        to_d = date_to or today
        from_d = date_from or (to_d - timedelta(days=29))
        return (datetime.combine(from_d, time.min).replace(tzinfo=timezone.utc),
                datetime.combine(to_d, time.max).replace(tzinfo=timezone.utc))

    # ---------- catalog ----------
    def catalog(self) -> dict:
        return {
            "personas": list(PERSONAS),
            "scopes": list(SCOPES),
            "widgets": [{"id": wid, **meta} for wid, meta in WIDGET_CATALOG.items()],
            "persona_layouts": PERSONA_LAYOUTS,
        }

    def default_persona(self, actor: User) -> str:
        return "ceo" if actor.role in ("SuperAdmin", "OrgAdmin") else "operations"

    # ================= widget composers (all reuse existing services) =================
    async def _revenue(self, actor, start, end, sd, ed) -> dict:
        from app.services.org_analytics_service import OrganizationAnalyticsService
        ov = await OrganizationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)
        return {"revenue": ov.get("revenue", 0.0), "leads": ov.get("leads", 0),
                "converted": ov.get("converted", 0), "conversion_rate": ov.get("conversion_rate", 0.0)}

    async def _conversion(self, actor, start, end, sd, ed) -> dict:
        from app.services.org_analytics_service import OrganizationAnalyticsService
        ov = await OrganizationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)
        return {"conversion_rate": ov.get("conversion_rate", 0.0), "leads": ov.get("leads", 0),
                "converted": ov.get("converted", 0)}

    async def _pipeline(self, actor, start, end, sd, ed) -> dict:
        from app.services.dashboard_service import DashboardService
        summ = await DashboardService(self.db).get_summary(actor)
        stages = summ.get("leads_by_stage", []) or []
        return {"by_stage": stages, "total": sum(s.get("count", 0) for s in stages),
                "conversion_rate": summ.get("conversion_rate", 0.0)}

    async def _lead_sources(self, actor, start, end, sd, ed) -> dict:
        from app.services.dashboard_service import DashboardService
        summ = await DashboardService(self.db).get_summary(actor)
        return {"by_source": summ.get("leads_by_source", []) or []}

    async def _collections(self, actor, start, end, sd, ed) -> dict:
        from app.services.customer_service import CustomerService
        rep = await CustomerService(self.db).get_report(actor, date_from=start, date_to=end)
        invoiced = rep.get("total_invoiced", 0.0)
        collected = rep.get("total_collected", 0.0)
        return {"invoiced": invoiced, "collected": collected,
                "outstanding": rep.get("outstanding_ar", 0.0), "overdue": rep.get("overdue_ar", 0.0),
                "collection_rate": round(collected * 100 / invoiced, 1) if invoiced else 0.0,
                "invoices_by_status": rep.get("invoices_by_status", [])}

    async def _cash_flow(self, actor, start, end, sd, ed) -> dict:
        """NEW. A cash position from AR: realised inflow (collected), expected
        inflow (outstanding), at-risk (overdue), and a simple healthy projection."""
        from app.services.customer_service import CustomerService
        rep = await CustomerService(self.db).get_report(actor, date_from=start, date_to=end)
        collected = rep.get("total_collected", 0.0)
        outstanding = rep.get("outstanding_ar", 0.0)
        overdue = rep.get("overdue_ar", 0.0)
        expected_soon = max(0.0, outstanding - overdue)   # not-yet-overdue receivables
        return {"realised_inflow": collected, "expected_inflow": outstanding, "at_risk": overdue,
                "projected_healthy_inflow": expected_soon,
                "net_position": round(collected + expected_soon, 2)}

    async def _forecast(self, actor, start, end, sd, ed) -> dict:
        """NEW. Weighted pipeline forecast: open pipeline value × current
        conversion rate, added to realised revenue."""
        from app.services.org_analytics_service import OrganizationAnalyticsService
        ov = await OrganizationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)
        conv = ov.get("conversion_rate", 0.0) or 0.0
        realised = ov.get("revenue", 0.0) or 0.0
        open_value = (await self.db.execute(select(func.coalesce(func.sum(Lead.value), 0)).filter(
            Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
            Lead.converted_at.is_(None), Lead.is_archived == False))).scalar() or 0
        open_value = float(open_value)
        weighted = round(open_value * conv / 100.0, 2)
        return {"open_pipeline_value": round(open_value, 2), "conversion_rate": conv,
                "weighted_pipeline": weighted, "realised_revenue": round(realised, 2),
                "projected_total": round(realised + weighted, 2)}

    async def _communication_summary(self, actor, start, end, sd, ed) -> dict:
        from app.services.communication_analytics_service import CommunicationAnalyticsService
        return await CommunicationAnalyticsService(self.db).overview(actor, date_from=start, date_to=end)

    async def _call_statistics(self, actor, start, end, sd, ed) -> dict:
        from app.services.communication_analytics_service import CommunicationAnalyticsService
        svc = CommunicationAnalyticsService(self.db)
        ov = await svc.overview(actor, channel="Call", date_from=start, date_to=end)
        missed = await svc.missed(actor, date_from=start, date_to=end)
        talk = await svc.talk_time(actor, date_from=start, date_to=end)
        return {"total_calls": ov.get("total", 0), "outbound": ov.get("outbound", 0),
                "inbound": ov.get("inbound", 0), "connected": ov.get("delivered", 0),
                "missed": missed.get("missed", missed.get("total", 0)) if isinstance(missed, dict) else 0,
                "talk_time": talk}

    async def _agent_productivity(self, actor, start, end, sd, ed) -> dict:
        from app.services.communication_analytics_service import CommunicationAnalyticsService
        agents = await CommunicationAnalyticsService(self.db).agents(actor, date_from=start, date_to=end)
        agents = sorted(agents, key=lambda a: -a.get("total", 0))[:8]
        return {"agents": agents}

    async def _department_performance(self, actor, start, end, sd, ed, scope="organization") -> dict:
        from app.services.org_analytics_service import OrganizationAnalyticsService
        kind = {"branch": "branch", "team": "team"}.get(scope, "department")
        try:
            rows = await OrganizationAnalyticsService(self.db).domain(actor, kind, date_from=sd, date_to=ed)
        except HTTPException:
            rows = []
        return {"dimension": kind, "rows": rows[:12]}

    async def _target_achievement(self, actor, start, end, sd, ed) -> dict:
        from app.services.target_service import TargetService
        d = await TargetService(self.db).dashboard(actor)
        return {"avg_attainment": d.get("avg_attainment", 0.0), "on_track": d.get("on_track", 0),
                "missed": d.get("missed", 0), "total": d.get("total", 0), "by_scope": d.get("by_scope", [])}

    async def _attendance(self, actor, start, end, sd, ed) -> dict:
        from app.services.org_analytics_service import OrganizationAnalyticsService
        ov = await OrganizationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)
        return {"headcount": ov.get("headcount", 0), "present_today": ov.get("present_today", 0),
                "attendance_rate": ov.get("attendance_rate", 0.0), "on_leave_today": ov.get("on_leave_today", 0)}

    async def _leave(self, actor, start, end, sd, ed) -> dict:
        from app.services.org_analytics_service import OrganizationAnalyticsService
        ov = await OrganizationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)
        return {"pending_leaves": ov.get("pending_leaves", 0), "on_leave_today": ov.get("on_leave_today", 0)}

    async def _automation_overview(self, actor, start, end, sd, ed) -> dict:
        from app.services.automation_analytics_service import AutomationAnalyticsService
        return await AutomationAnalyticsService(self.db).overview(actor, date_from=sd, date_to=ed)

    async def _workflow_status(self, actor, start, end, sd, ed) -> dict:
        ov = await self._automation_overview(actor, start, end, sd, ed)
        return ov.get("workflow", {})

    async def _automation_health(self, actor, start, end, sd, ed) -> dict:
        ov = await self._automation_overview(actor, start, end, sd, ed)
        return {"jobs": ov.get("automation_jobs", {}), "queue": ov.get("queue", {}), "rules": ov.get("rules", {})}

    async def _sla_compliance(self, actor, start, end, sd, ed) -> dict:
        ov = await self._automation_overview(actor, start, end, sd, ed)
        return ov.get("sla", {})

    async def _escalations(self, actor, start, end, sd, ed) -> dict:
        ov = await self._automation_overview(actor, start, end, sd, ed)
        return ov.get("escalation", {})

    async def _campaign_performance(self, actor, start, end, sd, ed) -> dict:
        from app.services.campaign_service import CampaignService
        return await CampaignService(self.db).dashboard(actor)

    async def _customer_satisfaction(self, actor, start, end, sd, ed) -> dict:
        """NEW. A CSAT proxy from support tickets: resolution rate, avg resolution
        time and open/critical load (no survey table exists yet)."""
        org = actor.organization_id
        rows = (await self.db.execute(select(SupportTicket.status, func.count(SupportTicket.id)).filter(
            SupportTicket.organization_id == org, SupportTicket.created_at >= start,
            SupportTicket.created_at <= end).group_by(SupportTicket.status))).all()
        by_status = {s: n for s, n in rows}
        total = sum(by_status.values())
        resolved = by_status.get("Resolved", 0) + by_status.get("Closed", 0)
        open_tickets = by_status.get("Open", 0) + by_status.get("In_Progress", 0)
        critical_open = (await self.db.execute(select(func.count(SupportTicket.id)).filter(
            SupportTicket.organization_id == org, SupportTicket.priority == "Critical",
            SupportTicket.status.in_(["Open", "In_Progress"])))).scalar() or 0
        pairs = (await self.db.execute(select(SupportTicket.created_at, SupportTicket.resolved_at).filter(
            SupportTicket.organization_id == org, SupportTicket.resolved_at.isnot(None),
            SupportTicket.created_at >= start, SupportTicket.created_at <= end))).all()
        hrs = [(_aware(r) - _aware(c)).total_seconds() / 3600 for c, r in pairs if c and r]
        resolution_rate = round(resolved * 100 / total, 1) if total else 0.0
        return {"total": total, "resolved": resolved, "open": open_tickets, "critical_open": critical_open,
                "resolution_rate": resolution_rate,
                "avg_resolution_hours": round(sum(hrs) / len(hrs), 1) if hrs else 0.0,
                "csat_proxy": resolution_rate, "source": "support_tickets"}

    async def _ai_insights(self, actor, start, end, sd, ed) -> dict:
        """NEW. A rules-based executive insight generator over the key blocks —
        a deterministic stand-in that the dashboard exposes as AI-ready. No LLM
        call; the shape is stable so a model-backed generator can drop in later."""
        insights: list[dict] = []
        try:
            rev = await self._revenue(actor, start, end, sd, ed)
            if rev.get("conversion_rate", 0) and rev["conversion_rate"] < 20:
                insights.append({"severity": "warning", "title": "Low lead conversion",
                                 "detail": f"Conversion is {rev['conversion_rate']}% — review lead qualification and follow-up.",
                                 "drill": "/org-analytics"})
        except Exception:
            pass
        try:
            cf = await self._cash_flow(actor, start, end, sd, ed)
            if cf.get("at_risk", 0) > 0:
                insights.append({"severity": "critical", "title": "Overdue receivables",
                                 "detail": f"₹{round(cf['at_risk']):,} is overdue — prioritise collections.",
                                 "drill": "/customers"})
        except Exception:
            pass
        try:
            sla = await self._sla_compliance(actor, start, end, sd, ed)
            if sla.get("open_breaches", 0) > 0:
                insights.append({"severity": "warning", "title": "Open SLA breaches",
                                 "detail": f"{sla['open_breaches']} SLA breach(es) open — check the SLA board.",
                                 "drill": "/sla"})
        except Exception:
            pass
        try:
            att = await self._attendance(actor, start, end, sd, ed)
            if att.get("headcount", 0) and att.get("attendance_rate", 100) < 80:
                insights.append({"severity": "info", "title": "Attendance below target",
                                 "detail": f"Attendance is {att['attendance_rate']}% today.",
                                 "drill": "/attendance"})
        except Exception:
            pass
        try:
            fc = await self._forecast(actor, start, end, sd, ed)
            if fc.get("weighted_pipeline", 0) > 0:
                insights.append({"severity": "info", "title": "Pipeline forecast",
                                 "detail": f"Weighted pipeline adds ₹{round(fc['weighted_pipeline']):,} to a projected ₹{round(fc['projected_total']):,}.",
                                 "drill": "/org-analytics"})
        except Exception:
            pass
        if not insights:
            insights.append({"severity": "info", "title": "All clear",
                             "detail": "No pressing executive alerts in this window.", "drill": None})
        return {"ai_ready": True, "generated_at": _now().isoformat(), "insights": insights}

    _COMPOSERS = {
        "revenue": "_revenue", "conversion_rate": "_conversion", "pipeline": "_pipeline",
        "lead_sources": "_lead_sources", "collections": "_collections", "cash_flow": "_cash_flow",
        "forecast": "_forecast", "communication_summary": "_communication_summary",
        "call_statistics": "_call_statistics", "agent_productivity": "_agent_productivity",
        "department_performance": "_department_performance", "target_achievement": "_target_achievement",
        "attendance": "_attendance", "leave": "_leave", "workflow_status": "_workflow_status",
        "automation_health": "_automation_health", "sla_compliance": "_sla_compliance",
        "escalations": "_escalations", "campaign_performance": "_campaign_performance",
        "customer_satisfaction": "_customer_satisfaction", "ai_insights": "_ai_insights",
    }

    async def compose(self, actor: User, widgets: list[str] | None = None, *, persona: str | None = None,
                      scope: str = "organization", date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        persona = persona if persona in PERSONAS else None
        if not widgets:
            widgets = PERSONA_LAYOUTS.get(persona or self.default_persona(actor), PERSONA_LAYOUTS["ceo"])
        if scope not in SCOPES:
            scope = "organization"
        start, end = self._window(date_from, date_to)
        blocks: dict = {}
        for wid in widgets:
            fn = self._COMPOSERS.get(wid)
            if not fn:
                continue
            try:
                if wid == "department_performance":
                    blocks[wid] = await self._department_performance(actor, start, end, date_from, date_to, scope=scope)
                else:
                    blocks[wid] = await getattr(self, fn)(actor, start, end, date_from, date_to)
            except HTTPException:
                raise
            except Exception as e:  # a broken subsystem must not sink the cockpit
                blocks[wid] = {"error": str(e)[:200]}
        return {"persona": persona or self.default_persona(actor), "scope": scope,
                "from": start.date().isoformat(), "to": end.date().isoformat(),
                "generated_at": _now().isoformat(), "widgets": widgets, "blocks": blocks}

    # ================= saved views (widget configuration) =================
    async def list_views(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(DashboardView).filter(
            DashboardView.organization_id == actor.organization_id, DashboardView.user_id == actor.id,
            DashboardView.is_deleted == False).order_by(DashboardView.created_at.asc()))).scalars().all()
        return [self._serialize_view(v) for v in rows]

    async def create_view(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        persona = data.get("persona") if data.get("persona") in PERSONAS else "custom"
        scope = data.get("scope") if data.get("scope") in SCOPES else "organization"
        widgets = [w for w in (data.get("widgets") or []) if w in WIDGET_CATALOG]
        if not widgets:
            widgets = PERSONA_LAYOUTS.get(persona, PERSONA_LAYOUTS["ceo"])
        v = DashboardView(organization_id=actor.organization_id, user_id=actor.id, name=data["name"],
                          persona=persona, scope=scope, widgets=widgets,
                          is_default=bool(data.get("is_default", False)), created_by=actor.id)
        self.db.add(v)
        await self.db.flush()
        if v.is_default:
            await self._clear_other_defaults(actor, v.id)
        await self.db.refresh(v)
        return self._serialize_view(v)

    async def update_view(self, actor: User, view_id: uuid.UUID, data: dict) -> dict:
        v = await self._get_view(actor, view_id)
        if "name" in data and data["name"]:
            v.name = data["name"]
        if "persona" in data and data["persona"] in PERSONAS:
            v.persona = data["persona"]
        if "scope" in data and data["scope"] in SCOPES:
            v.scope = data["scope"]
        if "widgets" in data and data["widgets"] is not None:
            v.widgets = [w for w in data["widgets"] if w in WIDGET_CATALOG]
        if "is_default" in data and data["is_default"] is not None:
            v.is_default = bool(data["is_default"])
        self.db.add(v)
        await self.db.flush()
        if v.is_default:
            await self._clear_other_defaults(actor, v.id)
        await self.db.refresh(v)
        return self._serialize_view(v)

    async def delete_view(self, actor: User, view_id: uuid.UUID) -> None:
        v = await self._get_view(actor, view_id)
        v.is_deleted = True
        self.db.add(v)
        await self.db.flush()

    async def _get_view(self, actor: User, view_id: uuid.UUID) -> DashboardView:
        v = (await self.db.execute(select(DashboardView).filter(
            DashboardView.id == view_id, DashboardView.organization_id == actor.organization_id,
            DashboardView.user_id == actor.id, DashboardView.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
        return v

    async def _clear_other_defaults(self, actor: User, keep_id: uuid.UUID) -> None:
        others = (await self.db.execute(select(DashboardView).filter(
            DashboardView.organization_id == actor.organization_id, DashboardView.user_id == actor.id,
            DashboardView.is_deleted == False, DashboardView.is_default == True,
            DashboardView.id != keep_id))).scalars().all()
        for o in others:
            o.is_default = False
            self.db.add(o)
        await self.db.flush()

    def _serialize_view(self, v: DashboardView) -> dict:
        return {"id": str(v.id), "name": v.name, "persona": v.persona, "scope": v.scope,
                "widgets": v.widgets or [], "is_default": v.is_default,
                "created_at": v.created_at.isoformat() if v.created_at else None}

    # ================= export =================
    async def export_csv(self, actor: User, widgets=None, persona=None, scope="organization",
                         date_from=None, date_to=None) -> str:
        data = await self.compose(actor, widgets, persona=persona, scope=scope,
                                  date_from=date_from, date_to=date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Executive dashboard", f"persona={data['persona']}", f"scope={data['scope']}",
                    f"{data['from']} → {data['to']}"])
        w.writerow([])
        w.writerow(["Widget", "Metric", "Value"])
        for wid, block in data["blocks"].items():
            label = WIDGET_CATALOG.get(wid, {}).get("label", wid)
            if not isinstance(block, dict):
                continue
            for k, val in block.items():
                if isinstance(val, (list, dict)):
                    continue  # flatten only scalar metrics
                w.writerow([label, k, val])
        return buf.getvalue()

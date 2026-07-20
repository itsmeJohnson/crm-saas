"""AI Sales Intelligence.

Deal- and pipeline-level intelligence that unifies the CRM's sales signals —
reusing rather than re-implementing:

* win probability + factor breakdown → PredictiveService lead features/heuristic
* pipeline insights (funnel / win-rate / velocity / lost reasons) → SalesAnalyticsService
* revenue prediction → ForecastingService (revenue forecast + pipeline forecast)
* upsell / cross-sell candidates → PredictiveService customer aggregates
* generative pieces (deal summary, sales coaching, objection handling, proposal,
  quotation cover note) → the AI Platform gateway (multi-provider, cost-tracked)

Deals are the open pipeline leads. On top it derives sales risk, loss
prediction and a rule-based competitor analysis (lost-reason + text mentions).
NO new tables, no cron, no AI hardcoding — a bounded read aggregator, manager-
scoped (downline) like the analytics modules.
"""
from __future__ import annotations
import csv
import io
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.note import Note
from app.services.predictive_service import PredictiveService, _clamp
from app.services.sales_analytics_service import SalesAnalyticsService
from app.services.forecasting_service import ForecastingService

WON_STATUSES = {"Won", "Converted", "Customer"}
LOST_STATUSES = {"Lost"}
MAX_DEALS = 5000

# Known competitor keywords are org-agnostic seeds; the scan also flags any token
# appearing after "competitor"/"lost to" in lost reasons and notes.
COMPETITOR_SEEDS = ("salesforce", "hubspot", "zoho", "pipedrive", "freshworks", "monday",
                    "dynamics", "sugarcrm", "insightly", "close.io", "copper")

# very small line-item catalog for auto-quotations (deterministic; a real
# product catalog would replace this)
DEFAULT_QUOTE_TERMS = "Valid for 30 days. Prices in INR, taxes extra."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class SalesIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pred = PredictiveService(db)
        self.sales = SalesAnalyticsService(db)
        self.forecast = ForecastingService(db)

    # ---------- scope ----------
    async def _scope_ids(self, actor: User) -> set | None:
        if actor.role in ("SuperAdmin", "OrgAdmin"):
            return None
        ids = {actor.id}
        if actor.role == "Manager":
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.is_deleted == False,
                User.reporting_to_id == actor.id))).scalars().all()
            ids |= set(rows)
        return ids

    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Sales intelligence is available to managers and admins only.")

    # ---------- per-deal intelligence ----------
    async def _get_deal(self, actor: User, lead_id: uuid.UUID) -> Lead:
        lead = (await self.db.execute(select(Lead).filter(
            Lead.id == lead_id, Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False))).scalars().first()
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        scope = await self._scope_ids(actor)
        if scope is not None and lead.assigned_user_id not in scope:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        return lead

    def _deal_intel(self, lead: Lead, f: dict) -> dict:
        win, factors = self.pred._lead_probability(f)
        value = _num(lead.value)
        expected_value = round(value * win / 100, 2)
        loss_risk = round(_clamp(100 - win, 0, 100), 1)
        # sales risk = likelihood the deal slips/stalls (distinct from loss)
        risk, risk_reasons = 0.0, []
        dsl = f["days_since_last_activity"]
        if f["activities_total"] == 0 and f["age_days"] > 7:
            risk += 30; risk_reasons.append("No engagement yet")
        elif dsl is not None and dsl > 21:
            risk += 25; risk_reasons.append(f"Stalled — {dsl} days since last touch")
        if f["age_days"] > 90:
            risk += 20; risk_reasons.append("Deal aging beyond 90 days")
        if win < 30:
            risk += 15; risk_reasons.append("Low win probability")
        stage = "won" if lead.status in WON_STATUSES else "lost" if lead.status in LOST_STATUSES else "open"
        health = "strong" if win >= 60 and risk < 30 else "at_risk" if (risk >= 50 or win < 30) else "moderate"
        return {"lead_id": str(lead.id), "name": f["name"], "status": lead.status, "stage": stage,
                "value": value, "win_probability": win, "win_factors": factors,
                "loss_risk": loss_risk, "expected_value": expected_value,
                "sales_risk": round(_clamp(risk, 0, 100), 1), "sales_risk_reasons": risk_reasons,
                "health": health, "recommended_action": self._recommended_action(f, win, risk),
                "age_days": f["age_days"], "activities": f["activities_total"],
                "method": "heuristic_v1", "ai_ready": True}

    @staticmethod
    def _recommended_action(f: dict, win: float, risk: float) -> dict:
        if f["activities_total"] == 0:
            return {"action": "Make first contact", "priority": "high"}
        if win >= 60:
            return {"action": "Advance to proposal / close", "priority": "high"}
        if risk >= 50:
            return {"action": "Re-engage — deal is stalling", "priority": "high"}
        if win < 30:
            return {"action": "Qualify hard or disqualify", "priority": "medium"}
        return {"action": "Progress the next stage", "priority": "medium"}

    async def deal_intelligence(self, actor: User, lead_id: uuid.UUID) -> dict:
        lead = await self._get_deal(actor, lead_id)
        stats = await self.pred._lead_activity_stats(actor.organization_id)
        f = self.pred._lead_features(lead, stats)
        intel = self._deal_intel(lead, f)
        intel["competitors"] = await self._competitors_for_lead(actor, lead)
        return intel

    # ---------- generative (AI gateway) ----------
    def _gateway(self):
        from app.services.ai_gateway_service import AIGatewayService
        return AIGatewayService(self.db)

    async def deal_summary(self, actor: User, lead_id: uuid.UUID) -> dict:
        lead = await self._get_deal(actor, lead_id)
        return await self._gateway().crm_summarize(actor, "lead", str(lead.id))

    async def coaching(self, actor: User, lead_id: uuid.UUID) -> dict:
        lead = await self._get_deal(actor, lead_id)
        record = await self._gateway().build_context(actor, "lead", str(lead.id))
        stats = await self.pred._lead_activity_stats(actor.organization_id)
        f = self.pred._lead_features(lead, stats)
        intel = self._deal_intel(lead, f)
        return await self._gateway().generate(
            actor, task_type="crm",
            prompt=("You are a sales coach. Give a rep 3 concise, specific coaching tips to move this deal "
                    f"forward.\nWin probability: {intel['win_probability']}%. Sales risk: {intel['sales_risk']}.\n\n"
                    f"Deal:\n{record}"))

    async def objection_handling(self, actor: User, lead_id: uuid.UUID, objection: str) -> dict:
        lead = await self._get_deal(actor, lead_id)
        if not objection.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="objection text is required.")
        record = await self._gateway().build_context(actor, "lead", str(lead.id))
        return await self._gateway().generate(
            actor, task_type="crm",
            prompt=(f"A prospect raised this objection: \"{objection}\".\nWrite a concise, empathetic "
                    f"response that reframes and moves the deal forward.\n\nDeal context:\n{record}"))

    async def proposal(self, actor: User, lead_id: uuid.UUID) -> dict:
        lead = await self._get_deal(actor, lead_id)
        record = await self._gateway().build_context(actor, "lead", str(lead.id))
        return await self._gateway().generate(
            actor, task_type="report",
            prompt=("Write a short business proposal (problem, proposed solution, value, next steps) for "
                    f"this opportunity worth ₹{_num(lead.value):,.0f}.\n\n{record}"))

    async def quotation(self, actor: User, lead_id: uuid.UUID) -> dict:
        """Draft a quotation: deterministic line items derived from the deal
        value, plus an AI cover note."""
        lead = await self._get_deal(actor, lead_id)
        value = _num(lead.value) or 10000
        line_items = [
            {"description": "Primary solution / subscription", "qty": 1, "unit_price": round(value * 0.8, 2),
             "amount": round(value * 0.8, 2)},
            {"description": "Onboarding & implementation", "qty": 1, "unit_price": round(value * 0.15, 2),
             "amount": round(value * 0.15, 2)},
            {"description": "Support (annual)", "qty": 1, "unit_price": round(value * 0.05, 2),
             "amount": round(value * 0.05, 2)},
        ]
        subtotal = round(sum(li["amount"] for li in line_items), 2)
        tax = round(subtotal * 0.18, 2)
        cover = await self._gateway().generate(
            actor, task_type="communication",
            prompt=f"Write a 2-sentence quotation cover note for {lead.first_name or ''} {lead.last_name}.".strip())
        return {"lead_id": str(lead.id), "customer": f"{lead.first_name or ''} {lead.last_name}".strip(),
                "line_items": line_items, "subtotal": subtotal, "tax": tax,
                "total": round(subtotal + tax, 2), "currency": "INR", "terms": DEFAULT_QUOTE_TERMS,
                "cover_note": cover["text"]}

    # ---------- competitor analysis ----------
    async def _competitors_for_lead(self, actor: User, lead: Lead) -> list[str]:
        text = " ".join(filter(None, [lead.lost_reason, lead.company_name, lead.title])).lower()
        notes = (await self.db.execute(select(Note).filter(
            Note.lead_id == lead.id, Note.is_deleted == False).limit(20))).scalars().all()
        text += " " + " ".join((getattr(n, "content", "") or "").lower() for n in notes)
        return self._scan_competitors(text)

    @staticmethod
    def _scan_competitors(text: str) -> list[str]:
        found = {seed.title() for seed in COMPETITOR_SEEDS if seed in text}
        # buying-signal phrases reliably precede a competitor name (bare
        # "competitor X" is too often descriptive, so it's not a capture trigger).
        stop = {"the", "a", "an", "them", "us", "our", "here", "there", "another", "other",
                "someone", "their", "on", "at", "for", "with", "it", "this", "that", "price"}
        for m in re.finditer(r"(?:lost to|going with|chose|switched to|prefer|preferred)\s+([A-Za-z][\w.\-]{2,20})", text):
            token = m.group(1).strip(".")
            if token.lower() not in stop:
                found.add(token.title())
        return sorted(found)

    async def competitor_analysis(self, actor: User) -> dict:
        scope = await self._scope_ids(actor)
        q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False)
        if scope is not None:
            q = q.filter(Lead.assigned_user_id.in_(list(scope)))
        leads = list((await self.db.execute(q.limit(MAX_DEALS))).scalars().all())
        counts: dict[str, dict] = {}
        lost_to_competitor = 0
        for lead in leads:
            text = " ".join(filter(None, [lead.lost_reason, lead.company_name])).lower()
            comps = self._scan_competitors(text)
            is_lost = lead.status in LOST_STATUSES
            if comps and is_lost:
                lost_to_competitor += 1
            for c in comps:
                b = counts.setdefault(c, {"competitor": c, "mentions": 0, "lost_to": 0, "won_against": 0})
                b["mentions"] += 1
                if is_lost:
                    b["lost_to"] += 1
                elif lead.status in WON_STATUSES:
                    b["won_against"] += 1
        rows = sorted(counts.values(), key=lambda r: -r["mentions"])
        return {"competitors": rows, "lost_to_competitor": lost_to_competitor,
                "total_analyzed": len(leads)}

    # ---------- upsell / cross-sell ----------
    async def upsell_suggestions(self, actor: User) -> dict:
        """Upsell & cross-sell candidates from the customer base: high-CLV or
        long-tenure customers with headroom, and recently-active accounts."""
        self._require_manager(actor)
        customers = await self.pred._customers(actor.organization_id)
        upsell, cross_sell = [], []
        for c in customers:
            clv_churn, _ = self.pred._churn_risk(c)
            # upsell: healthy, paying customers with room to grow
            if c["total_paid"] > 0 and clv_churn < 50 and c["orders_count"] >= 1:
                upsell.append({"customer_id": c["customer_id"], "customer_name": c["customer_name"],
                               "reason": f"Healthy account (₹{c['total_paid']:,.0f} paid, {c['orders_count']} order(s)) — "
                                         f"propose a tier upgrade or add-on.",
                               "total_paid": c["total_paid"], "churn_risk": clv_churn,
                               "priority": "high" if c["total_paid"] >= 5000 else "medium"})
            # cross-sell: active but single-product (few orders) accounts
            if c["orders_count"] == 1 and c["activities_90d"] > 0:
                cross_sell.append({"customer_id": c["customer_id"], "customer_name": c["customer_name"],
                                   "reason": "Single-product account with recent engagement — introduce a complementary product.",
                                   "priority": "medium"})
        upsell.sort(key=lambda r: -r["total_paid"])
        return {"upsell": upsell[:20], "cross_sell": cross_sell[:20],
                "customers_analyzed": len(customers)}

    # ---------- pipeline insights + revenue prediction ----------
    async def pipeline_insights(self, actor: User) -> dict:
        self._require_manager(actor)
        overview = await self.sales.overview(actor)
        funnel = await self.sales.funnel(actor)
        velocity = await self.sales.velocity_and_cycle(actor)
        lost = await self.sales.lost_reasons(actor)
        return {"overview": overview, "funnel": funnel, "velocity": velocity, "lost_reasons": lost}

    async def revenue_prediction(self, actor: User) -> dict:
        self._require_manager(actor)
        revenue = await self.forecast.forecast(actor, metric="revenue", periods=6)
        pipeline = await self.forecast.pipeline_forecast(actor, periods=3)
        return {"revenue_forecast": revenue, "pipeline_forecast": pipeline}

    # ---------- deals list ----------
    async def _open_deals(self, actor: User) -> list[dict]:
        scope = await self._scope_ids(actor)
        q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
                                Lead.status.notin_(list(WON_STATUSES) + list(LOST_STATUSES)))
        if scope is not None:
            q = q.filter(Lead.assigned_user_id.in_(list(scope)))
        leads = list((await self.db.execute(q.order_by(Lead.created_at.desc()).limit(MAX_DEALS))).scalars().all())
        stats = await self.pred._lead_activity_stats(actor.organization_id)
        return [self._deal_intel(l, self.pred._lead_features(l, stats)) for l in leads]

    async def list_deals(self, actor: User, *, health: str | None = None, sort: str = "expected_value",
                         limit: int = 100) -> dict:
        rows = await self._open_deals(actor)
        if health:
            rows = [r for r in rows if r["health"] == health]
        key = {"expected_value": "expected_value", "win": "win_probability", "risk": "sales_risk",
               "value": "value"}.get(sort, "expected_value")
        rows.sort(key=lambda r: -r[key])
        return {"total": len(rows), "rows": rows[:min(limit, 500)]}

    # ---------- dashboard & report ----------
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        deals = await self._open_deals(actor)
        total = len(deals)
        weighted_pipeline = round(sum(d["expected_value"] for d in deals), 2)
        open_value = round(sum(d["value"] for d in deals), 2)
        by_health = {h: sum(1 for d in deals if d["health"] == h) for h in ("strong", "moderate", "at_risk")}
        avg_win = round(sum(d["win_probability"] for d in deals) / total, 1) if total else 0.0
        top_deals = sorted(deals, key=lambda d: -d["expected_value"])[:5]
        at_risk = sorted([d for d in deals if d["health"] == "at_risk"], key=lambda d: -d["sales_risk"])[:5]
        rev = await self.forecast.forecast(actor, metric="revenue", periods=3)
        return {"open_deals": total, "open_pipeline_value": open_value,
                "weighted_pipeline_value": weighted_pipeline, "avg_win_probability": avg_win,
                "by_health": by_health, "top_deals": top_deals, "at_risk_deals": at_risk,
                "revenue_forecast_next3": rev.get("forecast", [])[:3],
                "method": "heuristic_v1", "ai_ready": True}

    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        deals = await self._open_deals(actor)
        health = {h: sum(1 for d in deals if d["health"] == h) for h in ("strong", "moderate", "at_risk")}
        buckets = {"high (≥60%)": 0, "medium (30-59%)": 0, "low (<30%)": 0}
        for d in deals:
            w = d["win_probability"]
            buckets["high (≥60%)" if w >= 60 else "medium (30-59%)" if w >= 30 else "low (<30%)"] += 1
        competitor = await self.competitor_analysis(actor)
        return {"open_deals": len(deals), "by_health": health, "by_win_probability": buckets,
                "weighted_pipeline_value": round(sum(d["expected_value"] for d in deals), 2),
                "competitor": competitor}

    async def export_csv(self, actor: User) -> str:
        deals = await self._open_deals(actor)
        deals.sort(key=lambda d: -d["expected_value"])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["lead_id", "name", "status", "value", "win_probability", "loss_risk",
                    "expected_value", "sales_risk", "health", "recommended_action"])
        for d in deals:
            w.writerow([d["lead_id"], d["name"], d["status"], d["value"], d["win_probability"],
                        d["loss_risk"], d["expected_value"], d["sales_risk"], d["health"],
                        d["recommended_action"]["action"]])
        return buf.getvalue()

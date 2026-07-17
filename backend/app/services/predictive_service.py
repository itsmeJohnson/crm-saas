"""Predictive Analytics foundation — datasets, features and heuristic scores.

Deliberately NOT AI: this module prepares the ground a future model would stand
on. For each prediction target it engineers a structured, documented feature
matrix from existing transactional data (leads, activities, orders, invoices,
payments, contracts, users) with derivable labels for closed outcomes, exposes
them as training-dataset exports (CSV/JSON, audit-logged), and serves
prediction APIs whose scores are transparent deterministic heuristics
(`method: heuristic_v1`, factor breakdown included) that a trained model can
replace behind the same contracts (`ai_ready: true`). NO new tables, no cron —
a bounded read-only aggregator. Manager-gated like the analytics modules;
every dataset export writes a TRAINING_DATASET_EXPORTED audit event (surfaces
in Audit & Compliance under Data Exports).
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.company import Company
from app.models.customer_order import CustomerOrder
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.contract import Contract
from app.services.audit_service import AuditService

MAX_ENTITIES = 5000
WON_STATUSES = ("Converted", "Won")
LOST_STATUSES = ("Lost",)
PRIORITY_RANK = {"Low": 1, "Medium": 2, "High": 3, "Urgent": 4}

# Feature Engineering catalog — the documented schema of every dataset.
DATASETS: dict[str, dict] = {
    "lead_conversion": {
        "label": "Lead Prediction", "entity": "lead", "target": "converted (1/0, null while open)",
        "description": "One row per lead with engagement and firmographic features; closed leads carry the conversion label for training, open leads are scoring candidates.",
        "features": ["value", "score", "priority_rank", "source", "status", "age_days", "has_email",
                     "has_phone", "has_company", "activities_total", "calls", "emails",
                     "days_since_last_activity"]},
    "sales_pipeline": {
        "label": "Sales Prediction", "entity": "lead", "target": "won_value (closed) / expected_value (open)",
        "description": "Deal-level rows for revenue prediction: open pipeline with heuristic expected value, closed deals with realized outcome.",
        "features": ["value", "score", "priority_rank", "age_days", "activities_total", "calls",
                     "conversion_probability", "expected_value"]},
    "customer_churn": {
        "label": "Churn Prediction", "entity": "customer", "target": "churned (heuristic label, null when ambiguous)",
        "description": "One row per customer with recency/frequency/contract features; churned = no order or payment in 180d and no active contract.",
        "features": ["tenure_days", "orders_count", "total_paid", "avg_order_value", "last_order_days",
                     "last_payment_days", "active_contracts", "contracts_expiring_90d",
                     "activities_90d", "days_since_last_activity", "overdue_invoices", "churn_risk"]},
    "customer_clv": {
        "label": "Customer Lifetime Value", "entity": "customer", "target": "predicted_clv",
        "description": "Revenue history per customer with a deterministic 12-month CLV projection (historic value + monthly run-rate × retention factor).",
        "features": ["tenure_days", "total_paid", "total_invoiced", "orders_count", "avg_order_value",
                     "monthly_revenue", "churn_risk", "predicted_clv"]},
    "customer_risk": {
        "label": "Risk Score", "entity": "customer", "target": "risk_score (0-100)",
        "description": "Credit/payment risk per customer from overdue exposure, payment punctuality and open balance.",
        "features": ["invoices_count", "overdue_invoices", "overdue_ratio", "on_time_ratio",
                     "avg_payment_delay_days", "open_balance", "balance_ratio", "risk_score", "risk_band"]},
    "invoice_collection": {
        "label": "Collection Probability", "entity": "invoice", "target": "collection_probability (open) / paid_on_time (closed)",
        "description": "One row per invoice: open invoices carry an aging- and history-based collection probability; settled ones the on-time label.",
        "features": ["total_amount", "amount_paid", "balance", "days_overdue", "aging_bucket",
                     "customer_on_time_ratio", "collection_probability"]},
    "employee_performance": {
        "label": "Employee Performance Prediction", "entity": "user", "target": "predicted_next_30d_score",
        "description": "Per-employee activity composite for the last 30d vs the prior 30d, with a trend-projected next-period score.",
        "features": ["calls_30d", "conversions_30d", "tasks_30d", "activities_30d", "revenue_30d",
                     "attendance_30d", "score_30d", "score_prev_30d", "trend_pct", "predicted_next_30d_score"]},
    "recommendations": {
        "label": "Recommendation Engine", "entity": "lead|customer", "target": "next_best_action",
        "description": "Rule-based next-best-action feed over leads and customers (stale follow-ups, close pushes, renewals, collections, re-engagement).",
        "features": ["entity_type", "entity_id", "entity_name", "action", "reason", "priority"]},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _days_since(dt) -> int | None:
    dt = _aware(dt)
    return (_now() - dt).days if dt else None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class PredictiveService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Predictive analytics is available to managers and admins only.")

    # ---------- catalog (Feature Engineering documentation) ----------
    def catalog(self) -> dict:
        return {"method": "heuristic_v1", "ai_ready": True,
                "note": "Deterministic rule-based scores with documented factors — no ML. "
                        "The datasets are training-ready feature matrices a model can be fitted on later.",
                "datasets": [{"key": k, **v} for k, v in DATASETS.items()]}

    # ================= shared loaders (bounded, org-scoped) =================
    async def _lead_activity_stats(self, org_id) -> dict:
        rows = (await self.db.execute(
            select(Activity.lead_id, Activity.activity_type, func.count(Activity.id),
                   func.max(Activity.created_at))
            .filter(Activity.organization_id == org_id, Activity.is_deleted == False,
                    Activity.lead_id.isnot(None))
            .group_by(Activity.lead_id, Activity.activity_type))).all()
        stats: dict = {}
        for lead_id, atype, n, last in rows:
            s = stats.setdefault(lead_id, {"total": 0, "calls": 0, "emails": 0, "last": None})
            s["total"] += n
            if atype == "Call":
                s["calls"] += n
            if atype == "Email":
                s["emails"] += n
            if last and (s["last"] is None or last > s["last"]):
                s["last"] = last
        return stats

    async def _leads(self, org_id) -> tuple[list[Lead], dict]:
        leads = list((await self.db.execute(select(Lead).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False)
            .order_by(Lead.created_at.desc()).limit(MAX_ENTITIES))).scalars().all())
        return leads, await self._lead_activity_stats(org_id)

    def _lead_features(self, l: Lead, stats: dict) -> dict:
        s = stats.get(l.id, {"total": 0, "calls": 0, "emails": 0, "last": None})
        won = (l.status in WON_STATUSES) or (l.converted_at is not None)
        lost = l.status in LOST_STATUSES
        return {"lead_id": str(l.id), "name": f"{l.first_name or ''} {l.last_name or ''}".strip() or l.company_name or "—",
                "value": _num(l.value), "score": int(l.score or 0),
                "priority_rank": PRIORITY_RANK.get(l.priority, 2), "source": l.source, "status": l.status,
                "age_days": _days_since(l.created_at) or 0,
                "has_email": 1 if l.email else 0, "has_phone": 1 if l.phone else 0,
                "has_company": 1 if (l.company_id or l.company_name) else 0,
                "activities_total": s["total"], "calls": s["calls"], "emails": s["emails"],
                "days_since_last_activity": _days_since(s["last"]),
                "converted": 1 if won else (0 if lost else None)}

    def _lead_probability(self, f: dict) -> tuple[float, list[dict]]:
        factors = []

        def add(points, why):
            factors.append({"points": round(points, 1), "factor": why})
            return points

        p = add(25.0, "baseline")
        p += add(_clamp(f["score"] * 0.3, 0, 30), f"lead score {f['score']}")
        p += add(15 if f["calls"] >= 2 else (7 if f["calls"] == 1 else 0), f"{f['calls']} call(s) logged")
        p += add(8 if f["emails"] >= 1 else 0, f"{f['emails']} email(s) logged")
        p += add(4 if f["has_email"] else 0, "email on file")
        p += add(4 if f["has_company"] else 0, "company identified")
        p += add(3 * (f["priority_rank"] - 2), f"priority rank {f['priority_rank']}")
        dsl = f["days_since_last_activity"]
        p += add(-15 if (dsl is not None and dsl > 14) else 0, "no activity in 14+ days")
        p += add(-12 if (f["activities_total"] == 0 and f["age_days"] > 7) else 0, "never contacted")
        p += add(-10 if f["age_days"] > 60 else 0, "lead older than 60 days")
        return round(_clamp(p, 2, 95), 1), [x for x in factors if x["points"]]

    async def _customers(self, org_id) -> list[dict]:
        """Per-company customer aggregates (companies with any order-to-cash record)."""
        orders = (await self.db.execute(select(CustomerOrder).filter(
            CustomerOrder.organization_id == org_id, CustomerOrder.is_deleted == False,
            CustomerOrder.status != "Cancelled").limit(MAX_ENTITIES))).scalars().all()
        invoices = (await self.db.execute(select(CustomerInvoice).filter(
            CustomerInvoice.organization_id == org_id, CustomerInvoice.is_deleted == False,
            CustomerInvoice.status != "Void").limit(MAX_ENTITIES))).scalars().all()
        payments = (await self.db.execute(select(CustomerPayment).filter(
            CustomerPayment.organization_id == org_id,
            CustomerPayment.is_deleted == False).limit(MAX_ENTITIES))).scalars().all()
        contracts = (await self.db.execute(select(Contract).filter(
            Contract.organization_id == org_id, Contract.is_deleted == False).limit(MAX_ENTITIES))).scalars().all()
        act_rows = (await self.db.execute(
            select(Activity.company_id, func.count(Activity.id), func.max(Activity.created_at))
            .filter(Activity.organization_id == org_id, Activity.is_deleted == False,
                    Activity.company_id.isnot(None),
                    Activity.created_at >= _now() - timedelta(days=90))
            .group_by(Activity.company_id))).all()
        inv_by_id = {i.id: i for i in invoices}
        acts = {cid: {"count": n, "last": last} for cid, n, last in act_rows}

        agg: dict[uuid.UUID, dict] = {}

        def bucket(cid):
            return agg.setdefault(cid, {
                "orders_count": 0, "orders_total": 0.0, "last_order": None, "first_seen": None,
                "invoices_count": 0, "total_invoiced": 0.0, "total_paid_on_invoices": 0.0,
                "overdue_invoices": 0, "open_balance": 0.0,
                "payments_count": 0, "total_paid": 0.0, "last_payment": None,
                "on_time_payments": 0, "delays": [],
                "active_contracts": 0, "contracts_expiring_90d": 0})

        def see(b, dt):
            dt = _aware(dt)
            if dt and (b["first_seen"] is None or dt < b["first_seen"]):
                b["first_seen"] = dt

        today = _now()
        for o in orders:
            b = bucket(o.company_id)
            b["orders_count"] += 1
            b["orders_total"] += _num(o.total_amount)
            od = _aware(o.order_date or o.created_at)
            if od and (b["last_order"] is None or od > b["last_order"]):
                b["last_order"] = od
            see(b, o.order_date or o.created_at)
        for i in invoices:
            b = bucket(i.company_id)
            b["invoices_count"] += 1
            b["total_invoiced"] += _num(i.total_amount)
            b["total_paid_on_invoices"] += _num(i.amount_paid)
            balance = _num(i.total_amount) - _num(i.amount_paid)
            if i.status not in ("Paid",) and balance > 0:
                b["open_balance"] += balance
                if i.status == "Overdue" or (_aware(i.due_date) and _aware(i.due_date) < today):
                    b["overdue_invoices"] += 1
            see(b, i.issue_date or i.created_at)
        for p in payments:
            inv = inv_by_id.get(p.invoice_id)
            if not inv:
                continue
            b = bucket(inv.company_id)
            b["payments_count"] += 1
            b["total_paid"] += _num(p.amount)
            pd = _aware(p.paid_at or p.created_at)
            if pd and (b["last_payment"] is None or pd > b["last_payment"]):
                b["last_payment"] = pd
            due = _aware(inv.due_date)
            if pd and due:
                delay = (pd - due).days
                b["delays"].append(delay)
                if delay <= 0:
                    b["on_time_payments"] += 1
        for c in contracts:
            b = bucket(c.company_id)
            if c.status == "Active":
                b["active_contracts"] += 1
                if c.end_date and (c.end_date - today.date()).days <= 90:
                    b["contracts_expiring_90d"] += 1
            see(b, c.start_date and datetime(c.start_date.year, c.start_date.month, c.start_date.day,
                                             tzinfo=timezone.utc))

        if not agg:
            return []
        companies = {c.id: c for c in (await self.db.execute(select(Company).filter(
            Company.id.in_(list(agg.keys()))))).scalars().all()}
        out = []
        for cid, b in agg.items():
            a = acts.get(cid, {"count": 0, "last": None})
            tenure = _days_since(b["first_seen"]) or 0
            row = {"customer_id": str(cid),
                   "customer_name": companies[cid].name if cid in companies else "—",
                   "tenure_days": tenure, "orders_count": b["orders_count"],
                   "avg_order_value": round(b["orders_total"] / b["orders_count"], 2) if b["orders_count"] else 0.0,
                   "total_invoiced": round(b["total_invoiced"], 2),
                   "total_paid": round(b["total_paid"] or b["total_paid_on_invoices"], 2),
                   "invoices_count": b["invoices_count"], "overdue_invoices": b["overdue_invoices"],
                   "open_balance": round(b["open_balance"], 2),
                   "last_order_days": _days_since(b["last_order"]),
                   "last_payment_days": _days_since(b["last_payment"]),
                   "active_contracts": b["active_contracts"],
                   "contracts_expiring_90d": b["contracts_expiring_90d"],
                   "activities_90d": a["count"], "days_since_last_activity": _days_since(a["last"]),
                   "on_time_ratio": round(b["on_time_payments"] / b["payments_count"], 2) if b["payments_count"] else None,
                   "avg_payment_delay_days": round(sum(b["delays"]) / len(b["delays"]), 1) if b["delays"] else None}
            out.append(row)
        return out

    # ================= heuristic scores =================
    @staticmethod
    def _churn_risk(c: dict) -> tuple[float, list[dict]]:
        factors = []

        def add(points, why):
            if points:
                factors.append({"points": round(points, 1), "factor": why})
            return points

        risk = 0.0
        lod = c["last_order_days"]
        risk += add(_clamp((lod or 0) / 4.5, 0, 40) if lod is not None else 20,
                    f"last order {lod} day(s) ago" if lod is not None else "no orders on record")
        risk += add(20 if c["active_contracts"] == 0 else 0, "no active contract")
        dsl = c["days_since_last_activity"]
        risk += add(_clamp((dsl if dsl is not None else 90) / 6, 0, 25),
                    f"last touchpoint {dsl} day(s) ago" if dsl is not None else "no recent engagement")
        risk += add(10 if c["overdue_invoices"] > 0 else 0, f"{c['overdue_invoices']} overdue invoice(s)")
        return round(_clamp(risk, 0, 100), 1), factors

    @staticmethod
    def _churn_label(c: dict) -> int | None:
        lod, lpd = c["last_order_days"], c["last_payment_days"]
        stale = (lod is None or lod > 180) and (lpd is None or lpd > 180)
        if stale and c["active_contracts"] == 0:
            return 1
        dsl = c["days_since_last_activity"]
        if (lod is not None and lod <= 90) or (dsl is not None and dsl <= 90) or c["active_contracts"] > 0:
            return 0
        return None

    @staticmethod
    def _clv(c: dict, churn_risk: float, horizon_months: int = 12) -> dict:
        months = max(1.0, c["tenure_days"] / 30.0)
        monthly = c["total_paid"] / months
        retention = _clamp(1 - churn_risk / 150.0, 0.2, 1.0)
        predicted = round(c["total_paid"] + monthly * horizon_months * retention, 2)
        return {"monthly_revenue": round(monthly, 2), "retention_factor": round(retention, 2),
                "horizon_months": horizon_months, "predicted_clv": predicted}

    @staticmethod
    def _risk_score(c: dict, churn_risk: float) -> tuple[float, str]:
        overdue_ratio = c["overdue_invoices"] / c["invoices_count"] if c["invoices_count"] else 0.0
        late_ratio = 1 - (c["on_time_ratio"] if c["on_time_ratio"] is not None else 0.5)
        balance_ratio = c["open_balance"] / c["total_invoiced"] if c["total_invoiced"] else 0.0
        score = _clamp(overdue_ratio * 40 + late_ratio * 30 + balance_ratio * 20 + churn_risk * 0.1, 0, 100)
        band = "high" if score >= 60 else "medium" if score >= 30 else "low"
        return round(score, 1), band

    @staticmethod
    def _collection_probability(days_overdue: int, on_time_ratio: float | None, partially_paid: bool) -> float:
        if days_overdue <= 0:
            base = 90.0
        elif days_overdue <= 30:
            base = 72.0
        elif days_overdue <= 60:
            base = 55.0
        elif days_overdue <= 90:
            base = 35.0
        else:
            base = 18.0
        if on_time_ratio is not None:
            base += (on_time_ratio - 0.5) * 20  # ±10 by payment punctuality
        if partially_paid:
            base += 8
        return round(_clamp(base, 3, 97), 1)

    # ================= datasets =================
    async def dataset(self, actor: User, key: str, limit: int = 500) -> dict:
        self._require_manager(actor)
        if key not in DATASETS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown dataset. Allowed: {list(DATASETS)}")
        limit = max(1, min(int(limit), MAX_ENTITIES))
        rows = await getattr(self, f"_ds_{key}")(actor)
        rows = rows[:limit]
        columns = list(rows[0].keys()) if rows else DATASETS[key]["features"]
        return {"dataset": key, **{k: v for k, v in DATASETS[key].items() if k != "features"},
                "columns": columns, "rows": rows, "count": len(rows),
                "generated_at": _now().isoformat()}

    async def _ds_lead_conversion(self, actor: User) -> list[dict]:
        leads, stats = await self._leads(actor.organization_id)
        return [self._lead_features(l, stats) for l in leads]

    async def _ds_sales_pipeline(self, actor: User) -> list[dict]:
        leads, stats = await self._leads(actor.organization_id)
        out = []
        for l in leads:
            f = self._lead_features(l, stats)
            prob, _ = self._lead_probability(f)
            closed = f["converted"] is not None
            out.append({"lead_id": f["lead_id"], "name": f["name"], "value": f["value"],
                        "score": f["score"], "priority_rank": f["priority_rank"],
                        "age_days": f["age_days"], "activities_total": f["activities_total"],
                        "calls": f["calls"], "conversion_probability": None if closed else prob,
                        "expected_value": None if closed else round(f["value"] * prob / 100, 2),
                        "won_value": (f["value"] if f["converted"] == 1 else 0.0) if closed else None,
                        "outcome": ("won" if f["converted"] == 1 else "lost") if closed else "open"})
        return out

    async def _ds_customer_churn(self, actor: User) -> list[dict]:
        out = []
        for c in await self._customers(actor.organization_id):
            risk, _ = self._churn_risk(c)
            out.append({**{k: c[k] for k in ("customer_id", "customer_name", "tenure_days", "orders_count",
                                             "total_paid", "avg_order_value", "last_order_days",
                                             "last_payment_days", "active_contracts",
                                             "contracts_expiring_90d", "activities_90d",
                                             "days_since_last_activity", "overdue_invoices")},
                        "churn_risk": risk, "churned": self._churn_label(c)})
        return out

    async def _ds_customer_clv(self, actor: User) -> list[dict]:
        out = []
        for c in await self._customers(actor.organization_id):
            risk, _ = self._churn_risk(c)
            clv = self._clv(c, risk)
            out.append({**{k: c[k] for k in ("customer_id", "customer_name", "tenure_days", "total_paid",
                                             "total_invoiced", "orders_count", "avg_order_value")},
                        "monthly_revenue": clv["monthly_revenue"], "churn_risk": risk,
                        "predicted_clv": clv["predicted_clv"]})
        out.sort(key=lambda r: -r["predicted_clv"])
        return out

    async def _ds_customer_risk(self, actor: User) -> list[dict]:
        out = []
        for c in await self._customers(actor.organization_id):
            churn, _ = self._churn_risk(c)
            score, band = self._risk_score(c, churn)
            overdue_ratio = round(c["overdue_invoices"] / c["invoices_count"], 2) if c["invoices_count"] else 0.0
            balance_ratio = round(c["open_balance"] / c["total_invoiced"], 2) if c["total_invoiced"] else 0.0
            out.append({**{k: c[k] for k in ("customer_id", "customer_name", "invoices_count",
                                             "overdue_invoices", "on_time_ratio",
                                             "avg_payment_delay_days", "open_balance")},
                        "overdue_ratio": overdue_ratio, "balance_ratio": balance_ratio,
                        "risk_score": score, "risk_band": band})
        out.sort(key=lambda r: -r["risk_score"])
        return out

    async def _ds_invoice_collection(self, actor: User) -> list[dict]:
        org = actor.organization_id
        invoices = (await self.db.execute(select(CustomerInvoice).filter(
            CustomerInvoice.organization_id == org, CustomerInvoice.is_deleted == False,
            CustomerInvoice.status.notin_(("Draft", "Void")))
            .order_by(CustomerInvoice.created_at.desc()).limit(MAX_ENTITIES))).scalars().all()
        customers = {c["customer_id"]: c for c in await self._customers(org)}
        today = _now()
        out = []
        for i in invoices:
            cust = customers.get(str(i.company_id), {})
            due = _aware(i.due_date)
            days_overdue = (today - due).days if due else 0
            balance = round(_num(i.total_amount) - _num(i.amount_paid), 2)
            settled = i.status == "Paid" or balance <= 0
            bucket = ("current" if days_overdue <= 0 else "1-30" if days_overdue <= 30
                      else "31-60" if days_overdue <= 60 else "61-90" if days_overdue <= 90 else "90+")
            out.append({"invoice_id": str(i.id), "invoice_number": i.invoice_number,
                        "customer_id": str(i.company_id),
                        "customer_name": cust.get("customer_name", "—"),
                        "total_amount": _num(i.total_amount), "amount_paid": _num(i.amount_paid),
                        "balance": balance, "days_overdue": max(0, days_overdue), "aging_bucket": bucket,
                        "customer_on_time_ratio": cust.get("on_time_ratio"),
                        "collection_probability": None if settled else self._collection_probability(
                            days_overdue, cust.get("on_time_ratio"), _num(i.amount_paid) > 0),
                        "paid_on_time": (1 if days_overdue <= 0 or i.status == "Paid" else 0) if settled else None})
        return out

    async def _ds_employee_performance(self, actor: User) -> list[dict]:
        from app.services.performance_service import PerformanceService
        org = actor.organization_id
        users = (await self.db.execute(select(User).filter(
            User.organization_id == org, User.is_deleted == False, User.is_active == True)
            .limit(200))).scalars().all()
        perf = PerformanceService(self.db)
        today = _now().date()
        out = []
        for u in users:
            cur = await perf._user_metrics(org, u.id, today - timedelta(days=30), today)
            prev = await perf._user_metrics(org, u.id, today - timedelta(days=60), today - timedelta(days=30))

            def composite(m):
                return round(_num(m.get("calls_made")) * 0.5 + _num(m.get("leads_converted")) * 10
                             + _num(m.get("tasks_completed")) * 2 + _num(m.get("activities")) * 0.3
                             + _num(m.get("sales_revenue")) * 0.001, 2)

            cur_score, prev_score = composite(cur), composite(prev)
            trend = round((cur_score - prev_score) * 100 / prev_score, 1) if prev_score else (100.0 if cur_score else 0.0)
            predicted = round(cur_score * (1 + _clamp(trend / 100, -0.5, 0.5) * 0.5), 2)
            out.append({"user_id": str(u.id), "user_name": f"{u.first_name} {u.last_name}".strip(),
                        "role": u.role,
                        "calls_30d": _num(cur.get("calls_made")), "conversions_30d": _num(cur.get("leads_converted")),
                        "tasks_30d": _num(cur.get("tasks_completed")), "activities_30d": _num(cur.get("activities")),
                        "revenue_30d": _num(cur.get("sales_revenue")),
                        "attendance_30d": _num(cur.get("attendance_score")),
                        "score_30d": cur_score, "score_prev_30d": prev_score,
                        "trend_pct": trend, "predicted_next_30d_score": predicted})
        out.sort(key=lambda r: -r["score_30d"])
        return out

    async def _ds_recommendations(self, actor: User) -> list[dict]:
        recs: list[dict] = []
        leads, stats = await self._leads(actor.organization_id)
        for l in leads:
            f = self._lead_features(l, stats)
            if f["converted"] is not None:
                continue
            prob, _ = self._lead_probability(f)
            dsl = f["days_since_last_activity"]
            if f["activities_total"] == 0 and f["age_days"] >= 3:
                recs.append({"entity_type": "lead", "entity_id": f["lead_id"], "entity_name": f["name"],
                             "action": "Make first contact", "priority": "high",
                             "reason": f"Never contacted — created {f['age_days']} day(s) ago."})
            elif prob >= 60:
                recs.append({"entity_type": "lead", "entity_id": f["lead_id"], "entity_name": f["name"],
                             "action": "Push to close", "priority": "high",
                             "reason": f"{prob}% conversion likelihood — strike while warm."})
            elif f["score"] >= 50 and dsl is not None and dsl > 7:
                recs.append({"entity_type": "lead", "entity_id": f["lead_id"], "entity_name": f["name"],
                             "action": "Follow up", "priority": "medium",
                             "reason": f"Score {f['score']} lead idle for {dsl} day(s)."})
            elif f["age_days"] > 45 and prob < 30:
                recs.append({"entity_type": "lead", "entity_id": f["lead_id"], "entity_name": f["name"],
                             "action": "Qualify or archive", "priority": "low",
                             "reason": f"{f['age_days']} days old with {prob}% likelihood."})
        for c in await self._customers(actor.organization_id):
            churn, _ = self._churn_risk(c)
            if c["overdue_invoices"] > 0:
                recs.append({"entity_type": "customer", "entity_id": c["customer_id"],
                             "entity_name": c["customer_name"], "action": "Collect overdue balance",
                             "priority": "high",
                             "reason": f"{c['overdue_invoices']} overdue invoice(s), ₹{c['open_balance']:g} open."})
            if c["contracts_expiring_90d"] > 0:
                recs.append({"entity_type": "customer", "entity_id": c["customer_id"],
                             "entity_name": c["customer_name"], "action": "Start renewal conversation",
                             "priority": "high",
                             "reason": f"{c['contracts_expiring_90d']} contract(s) expiring within 90 days."})
            if churn >= 60:
                recs.append({"entity_type": "customer", "entity_id": c["customer_id"],
                             "entity_name": c["customer_name"], "action": "Re-engage customer",
                             "priority": "medium", "reason": f"Churn risk {churn} — long inactivity."})
        order = {"high": 0, "medium": 1, "low": 2}
        recs.sort(key=lambda r: order.get(r["priority"], 3))
        return recs[:100]

    # ================= training dataset export (audited) =================
    async def export_dataset(self, actor: User, key: str, fmt: str = "csv") -> tuple[bytes, str, str]:
        if fmt not in ("csv", "json"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be csv or json.")
        ds = await self.dataset(actor, key, limit=MAX_ENTITIES)
        if fmt == "json":
            import json
            content = json.dumps({"dataset": key, "generated_at": ds["generated_at"],
                                  "target": ds["target"], "columns": ds["columns"],
                                  "rows": ds["rows"]}, default=str).encode()
            mime = "application/json"
        else:
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(ds["columns"])
            for r in ds["rows"]:
                w.writerow([r.get(c) for c in ds["columns"]])
            content, mime = buf.getvalue().encode(), "text/csv"
        try:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id,
                action="TRAINING_DATASET_EXPORTED", resource_type="predictive",
                action_metadata={"dataset": key, "format": fmt, "rows": ds["count"]})
        except Exception:
            pass
        return content, mime, f"{key}.{fmt}"

    # ================= prediction APIs (heuristic, ai-ready contracts) =================
    def _envelope(self, kind: str, payload: dict) -> dict:
        return {"prediction": kind, "method": "heuristic_v1", "ai_ready": True,
                "generated_at": _now().isoformat(), **payload}

    async def predict_lead(self, actor: User, lead_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        l = (await self.db.execute(select(Lead).filter(
            Lead.id == lead_id, Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False))).scalars().first()
        if not l:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        stats = await self._lead_activity_stats(actor.organization_id)
        f = self._lead_features(l, stats)
        prob, factors = self._lead_probability(f)
        return self._envelope("lead_conversion", {
            "lead_id": str(lead_id), "conversion_probability": prob,
            "expected_value": round(f["value"] * prob / 100, 2),
            "features": f, "factors": factors})

    async def _customer_or_404(self, actor: User, company_id: uuid.UUID) -> dict:
        for c in await self._customers(actor.organization_id):
            if c["customer_id"] == str(company_id):
                return c
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Customer not found (no order-to-cash records).")

    async def predict_churn(self, actor: User, company_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        c = await self._customer_or_404(actor, company_id)
        risk, factors = self._churn_risk(c)
        band = "high" if risk >= 60 else "medium" if risk >= 30 else "low"
        return self._envelope("customer_churn", {"customer_id": str(company_id), "churn_risk": risk,
                                                 "band": band, "features": c, "factors": factors})

    async def predict_clv(self, actor: User, company_id: uuid.UUID, horizon_months: int = 12) -> dict:
        self._require_manager(actor)
        c = await self._customer_or_404(actor, company_id)
        risk, _ = self._churn_risk(c)
        clv = self._clv(c, risk, horizon_months=max(1, min(int(horizon_months), 60)))
        return self._envelope("customer_clv", {"customer_id": str(company_id), **clv,
                                               "historic_value": c["total_paid"], "churn_risk": risk,
                                               "features": c})

    async def predict_risk(self, actor: User, company_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        c = await self._customer_or_404(actor, company_id)
        churn, _ = self._churn_risk(c)
        score, band = self._risk_score(c, churn)
        return self._envelope("customer_risk", {"customer_id": str(company_id), "risk_score": score,
                                                "risk_band": band, "features": c})

    async def predict_collection(self, actor: User, invoice_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        rows = await self._ds_invoice_collection(actor)
        row = next((r for r in rows if r["invoice_id"] == str(invoice_id)), None)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        return self._envelope("invoice_collection", {**row})

    async def predict_employee(self, actor: User, user_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        rows = await self._ds_employee_performance(actor)
        row = next((r for r in rows if r["user_id"] == str(user_id)), None)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._envelope("employee_performance", {**row})

    async def recommendations(self, actor: User, scope: str = "all", limit: int = 25) -> list[dict]:
        self._require_manager(actor)
        recs = await self._ds_recommendations(actor)
        if scope in ("lead", "leads"):
            recs = [r for r in recs if r["entity_type"] == "lead"]
        elif scope in ("customer", "customers"):
            recs = [r for r in recs if r["entity_type"] == "customer"]
        return recs[:max(1, min(int(limit), 100))]

    # ================= dashboard =================
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        leads = await self._ds_sales_pipeline(actor)
        open_leads = [l for l in leads if l["outcome"] == "open"]
        hot = sorted(open_leads, key=lambda r: -(r["conversion_probability"] or 0))[:5]
        churn_rows = await self._ds_customer_churn(actor)
        at_risk = sorted(churn_rows, key=lambda r: -r["churn_risk"])[:5]
        inv = await self._ds_invoice_collection(actor)
        open_inv = [r for r in inv if r["collection_probability"] is not None]
        low_collection = [r for r in open_inv if r["collection_probability"] < 50]
        recs = await self._ds_recommendations(actor)
        expected_pipeline = round(sum(r["expected_value"] or 0 for r in open_leads), 2)
        return {"method": "heuristic_v1", "ai_ready": True,
                "datasets": {k: v["label"] for k, v in DATASETS.items()},
                "open_leads": len(open_leads), "expected_pipeline_value": expected_pipeline,
                "customers_tracked": len(churn_rows),
                "customers_at_high_churn_risk": sum(1 for r in churn_rows if r["churn_risk"] >= 60),
                "open_invoices": len(open_inv), "invoices_at_collection_risk": len(low_collection),
                "recommendations": len(recs),
                "hot_leads": hot, "at_risk_customers": at_risk,
                "top_recommendations": recs[:6]}

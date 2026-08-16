"""AI Prediction Engine — the unifying prediction layer.

COMPOSES the existing predictive stack rather than reimplementing it:
  * PredictiveService  → lead / churn / collection / employee predictions +
    training-ready feature datasets and their labels.
  * ForecastingService → revenue / sales time-series projection + holdout
    backtest (regression accuracy / MAPE).

On top of that it adds what the foundation lacked:
  * a versioned MODEL REGISTRY (code-level, NO new tables) so every prediction
    reports which model + version produced it;
  * a deterministic CONFIDENCE SCORE on every prediction (data completeness ×
    sample size × signal strength);
  * two NEW predictors — TASK DELAY (over tasks) and CAMPAIGN (over campaigns);
  * a unified SALES prediction (pipeline expectation + projection);
  * FORECAST ACCURACY across both regression (backtest) and classification
    (calibration on labelled lead/churn data);
  * a consolidated cross-model REPORT + CSV export.

Everything is deterministic. The AI gateway is intentionally not required here —
these are quantitative predictions; the `ai_ready` envelopes remain compatible
with a trained model swap later.
"""
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.task import Task
from app.models.campaign import Campaign
from app.services.audit_service import AuditService
from app.services.predictive_service import PredictiveService
from app.services.forecasting_service import ForecastingService

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
ENGINE_VERSION = "prediction_engine_v1"
ALGORITHM = "heuristic_v1"

# ---- Model registry: versioned metadata for every prediction the engine serves.
# No training artefact today (algorithm=heuristic_v1) but the shape is what a
# fitted model would report, so callers can already branch on model/version.
MODEL_REGISTRY: dict[str, dict] = {
    "lead_conversion": {
        "name": "Lead Conversion Predictor", "version": "1.3.0", "type": "classification",
        "target": "will the open lead convert", "unit": "probability %",
        "features": ["score", "value", "priority_rank", "age_days", "activities_total", "calls",
                     "has_email", "has_phone", "org_conversion_rate"]},
    "sales_pipeline": {
        "name": "Sales / Pipeline Predictor", "version": "1.1.0", "type": "regression",
        "target": "expected pipeline close value and near-term sales", "unit": "currency",
        "features": ["open_pipeline_value", "weighted_expected_value", "win_rate", "sales_trend"]},
    "revenue": {
        "name": "Revenue Forecaster", "version": "1.2.0", "type": "timeseries",
        "target": "future revenue per period", "unit": "currency",
        "features": ["revenue_history", "trend", "seasonality"]},
    "customer_churn": {
        "name": "Customer Churn Predictor", "version": "1.2.0", "type": "classification",
        "target": "customer will churn", "unit": "risk %",
        "features": ["tenure_days", "last_order_days", "last_payment_days", "active_contracts",
                     "contracts_expiring_90d", "activities_90d", "overdue_invoices"]},
    "invoice_collection": {
        "name": "Collection Predictor", "version": "1.1.0", "type": "classification",
        "target": "open invoice will be collected", "unit": "probability %",
        "features": ["days_overdue", "aging_bucket", "customer_on_time_ratio", "partially_paid"]},
    "task_delay": {
        "name": "Task Delay Predictor", "version": "1.0.0", "type": "classification",
        "target": "open task will miss its due date", "unit": "risk %",
        "features": ["hours_to_due", "status", "priority_rank", "assignee_on_time_rate",
                     "assignee_open_load", "checklist_completion"]},
    "employee_performance": {
        "name": "Employee Performance Predictor", "version": "1.1.0", "type": "regression",
        "target": "projected performance score", "unit": "score 0-100",
        "features": ["goal_attainment", "activities", "conversions", "task_completion"]},
    "campaign_response": {
        "name": "Campaign Response Predictor", "version": "1.0.0", "type": "regression",
        "target": "expected delivery / open / click / conversion / ROI", "unit": "rates + ROI",
        "features": ["channel", "audience_size", "channel_benchmarks", "historical_conversion"]},
}
CLASSIFICATION_MODELS = tuple(k for k, m in MODEL_REGISTRY.items() if m["type"] == "classification")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _rate(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def confidence_score(*, sample_size: int, completeness: float, signal_strength: float,
                     sample_target: int = 20) -> dict:
    """Deterministic confidence in a prediction, 0-100, from three factors:
      * sample_size  — how much data backs the estimate (saturating at target);
      * completeness — fraction of the model's features that were populated (0-1);
      * signal_strength — how decisive the evidence is, e.g. distance of a
        probability from the 50/50 coin-flip, or |trend| (0-1).
    Weighted 0.35 / 0.35 / 0.30. Returned with a band for display."""
    sample_factor = min(1.0, sample_size / max(1, sample_target))
    completeness = _clamp(completeness, 0.0, 1.0)
    signal_strength = _clamp(signal_strength, 0.0, 1.0)
    score = round(100 * (0.35 * sample_factor + 0.35 * completeness + 0.30 * signal_strength), 1)
    band = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {"confidence": score, "confidence_band": band,
            "confidence_factors": {"sample_size": sample_size,
                                   "sample_factor": round(sample_factor, 2),
                                   "feature_completeness": round(completeness, 2),
                                   "signal_strength": round(signal_strength, 2)}}


class PredictionEngineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.predictive = PredictiveService(db)
        self.forecasting = ForecastingService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    def _envelope(self, model_key: str, payload: dict, confidence: dict) -> dict:
        m = MODEL_REGISTRY[model_key]
        return {"model": model_key, "model_name": m["name"], "model_version": m["version"],
                "model_type": m["type"], "algorithm": ALGORITHM, "engine_version": ENGINE_VERSION,
                "ai_ready": True, "generated_at": _now().isoformat(),
                **confidence, **payload}

    # ================= model registry =================
    def models(self) -> dict:
        return {"engine_version": ENGINE_VERSION, "algorithm": ALGORITHM,
                "count": len(MODEL_REGISTRY),
                "models": [{"key": k, "status": "active", "trained_at": None, **v}
                           for k, v in MODEL_REGISTRY.items()]}

    # ================= composed predictions (add confidence + version) =======
    async def predict_lead(self, actor: User, lead_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        base = await self.predictive.predict_lead(actor, lead_id)
        f = base.get("features", {})
        prob = base.get("conversion_probability") or 0.0
        completeness = sum(1 for k in ("has_email", "has_phone", "score", "value")
                           if f.get(k)) / 4.0
        conf = confidence_score(sample_size=int(f.get("activities_total") or 0),
                                completeness=completeness,
                                signal_strength=abs(prob - 50) / 50.0, sample_target=10)
        return self._envelope("lead_conversion", {
            "lead_id": base["lead_id"], "conversion_probability": prob,
            "expected_value": base.get("expected_value"),
            "factors": base.get("factors"), "features": f}, conf)

    async def predict_churn(self, actor: User, company_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        base = await self.predictive.predict_churn(actor, company_id)
        f = base.get("features", {})
        risk = base.get("churn_risk") or 0.0
        completeness = sum(1 for k in ("tenure_days", "last_order_days", "orders_count")
                           if f.get(k) is not None) / 3.0
        conf = confidence_score(sample_size=int(f.get("orders_count") or 0),
                                completeness=completeness,
                                signal_strength=abs(risk - 50) / 50.0, sample_target=8)
        return self._envelope("customer_churn", {
            "customer_id": base["customer_id"], "churn_risk": risk, "band": base.get("band"),
            "factors": base.get("factors"), "features": f}, conf)

    async def predict_collection(self, actor: User, invoice_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        base = await self.predictive.predict_collection(actor, invoice_id)
        prob = base.get("collection_probability")
        otr = base.get("customer_on_time_ratio")
        completeness = (0.5 + 0.5 * (1 if otr is not None else 0))
        conf = confidence_score(sample_size=8 if otr is not None else 2,
                                completeness=completeness,
                                signal_strength=abs((prob if prob is not None else 50) - 50) / 50.0,
                                sample_target=8)
        return self._envelope("invoice_collection", {k: v for k, v in base.items()
                                                     if k not in ("prediction", "method", "ai_ready",
                                                                  "generated_at")}, conf)

    async def predict_employee(self, actor: User, user_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        base = await self.predictive.predict_employee(actor, user_id)
        payload = {k: v for k, v in base.items()
                   if k not in ("prediction", "method", "ai_ready", "generated_at")}
        activities = int(payload.get("activities") or payload.get("activities_total") or 0)
        conf = confidence_score(sample_size=activities, completeness=0.8,
                                signal_strength=0.6, sample_target=30)
        return self._envelope("employee_performance", payload, conf)

    async def predict_revenue(self, actor: User, periods: int = 6, granularity: str = "monthly") -> dict:
        self._require_manager(actor)
        fc = await self.forecasting.forecast(actor, metric="revenue", periods=periods,
                                             method="linear", granularity=granularity)
        back = await self.forecasting.historical_comparison(actor, metric="revenue",
                                                            granularity=granularity)
        history = fc.get("history", [])
        trend = fc.get("trend", {})
        # confidence from history depth, backtest accuracy and trend decisiveness
        acc = back.get("accuracy")
        conf = confidence_score(sample_size=len(history),
                                completeness=(acc / 100.0) if acc is not None else 0.5,
                                signal_strength=min(1.0, abs(trend.get("slope", 0.0)) or 0.2),
                                sample_target=12)
        return self._envelope("revenue", {
            "periods": periods, "granularity": granularity,
            "forecast": fc.get("forecast"), "total_forecast": fc.get("total_forecast"),
            "history_avg": fc.get("history_avg"), "trend": trend,
            "backtest_accuracy": acc, "backtest_mape": back.get("mape")}, conf)

    async def predict_sales(self, actor: User, periods: int = 3, granularity: str = "monthly") -> dict:
        """Unified sales prediction: open-pipeline expectation (from the lead
        conversion model) + a near-term sales-count projection."""
        self._require_manager(actor)
        rows = await self.predictive._ds_sales_pipeline(actor)
        open_rows = [r for r in rows if r["outcome"] == "open"]
        closed = [r for r in rows if r["outcome"] in ("won", "lost")]
        won = [r for r in closed if r["outcome"] == "won"]
        open_value = round(sum(r["value"] or 0 for r in open_rows), 2)
        weighted = round(sum(r["expected_value"] or 0 for r in open_rows), 2)
        win_rate = _rate(len(won), len(closed))
        fc = await self.forecasting.forecast(actor, metric="sales", periods=periods,
                                             method="linear", granularity=granularity)
        trend = fc.get("trend", {})
        conf = confidence_score(sample_size=len(closed),
                                completeness=1.0 if open_rows else 0.3,
                                signal_strength=min(1.0, abs(trend.get("slope", 0.0)) or 0.3),
                                sample_target=15)
        return self._envelope("sales_pipeline", {
            "open_deals": len(open_rows), "open_pipeline_value": open_value,
            "weighted_expected_value": weighted, "win_rate": win_rate,
            "sales_count_forecast": fc.get("forecast"),
            "expected_sales_next_periods": fc.get("total_forecast"),
            "trend": trend}, conf)

    # ================= NEW: task delay prediction =================
    def _task_delay(self, t: Task, now: datetime, assignee_on_time: float | None,
                    assignee_load: int) -> dict:
        due = _aware(t.due_date)
        checklist = t.checklist or []
        done = sum(1 for c in checklist if c.get("done"))
        checklist_completion = (done / len(checklist)) if checklist else None
        priority_rank = {"Urgent": 3, "High": 2, "Medium": 1, "Low": 0}.get(t.priority, 1)
        risk = 0.0
        factors: list[dict] = []

        def add(points, why):
            nonlocal risk
            risk += points
            factors.append({"factor": why, "impact": points})

        if due is None:
            # no due date → cannot be "late"; low, low-confidence risk
            base = {"task_id": str(t.id), "title": t.title, "status": t.status,
                    "due_date": None, "hours_to_due": None, "delay_risk": 0.0,
                    "band": "low", "factors": [{"factor": "no due date", "impact": 0}],
                    "predicted_late": False}
            return base
        hours_to_due = round((due - now).total_seconds() / 3600, 1)
        overdue = hours_to_due < 0
        if t.status in ("Done", "Cancelled"):
            completed = _aware(t.completed_at)
            was_late = bool(completed and due and completed > due)
            return {"task_id": str(t.id), "title": t.title, "status": t.status,
                    "due_date": due.isoformat(), "hours_to_due": hours_to_due,
                    "delay_risk": 100.0 if was_late else 0.0, "band": "n/a",
                    "resolved": True, "was_late": was_late,
                    "factors": [{"factor": "already closed", "impact": 0}],
                    "predicted_late": was_late}
        if overdue:
            add(55, f"already overdue by {abs(hours_to_due)}h")
        elif hours_to_due <= 24:
            add(28, "due within 24h and still open")
        elif hours_to_due <= 72:
            add(15, "due within 3 days")
        if t.status == "Todo":
            add(18, "not started yet")
        elif t.status == "InProgress":
            add(6, "in progress")
        add(priority_rank * 4, f"priority {t.priority}")
        if assignee_on_time is not None and assignee_on_time < 70:
            add(round((70 - assignee_on_time) * 0.3, 1),
                f"assignee on-time rate {assignee_on_time}%")
        if assignee_load >= 8:
            add(min(15, assignee_load - 7), f"assignee has {assignee_load} open tasks")
        if checklist_completion is not None and checklist_completion < 0.5 and not overdue:
            add(8, "checklist under half done")
        risk = round(_clamp(risk), 1)
        band = "high" if risk >= 60 else "medium" if risk >= 30 else "low"
        return {"task_id": str(t.id), "title": t.title, "status": t.status,
                "due_date": due.isoformat(), "hours_to_due": hours_to_due,
                "priority": t.priority, "assignee_on_time_rate": assignee_on_time,
                "assignee_open_load": assignee_load,
                "checklist_completion": (round(checklist_completion, 2)
                                         if checklist_completion is not None else None),
                "delay_risk": risk, "band": band, "factors": factors,
                "predicted_late": risk >= 50}

    async def _assignee_stats(self, org) -> tuple[dict, dict]:
        """Per-user historical on-time completion rate and current open-task load."""
        tasks = (await self.db.execute(select(Task).filter(
            Task.organization_id == org, Task.is_deleted == False))).scalars().all()
        closed_on_time: dict = {}
        closed_total: dict = {}
        open_load: dict = {}
        for t in tasks:
            uid = str(t.assigned_user_id) if t.assigned_user_id else None
            if uid is None:
                continue
            if t.status in ("Done", "Cancelled"):
                due, comp = _aware(t.due_date), _aware(t.completed_at)
                closed_total[uid] = closed_total.get(uid, 0) + 1
                on_time = not (due and comp and comp > due)
                closed_on_time[uid] = closed_on_time.get(uid, 0) + (1 if on_time else 0)
            elif t.status in ("Todo", "InProgress"):
                open_load[uid] = open_load.get(uid, 0) + 1
        on_time_rate = {uid: round(closed_on_time.get(uid, 0) * 100 / n, 1)
                        for uid, n in closed_total.items() if n}
        return on_time_rate, open_load

    async def predict_task(self, actor: User, task_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        t = (await self.db.execute(select(Task).filter(
            Task.id == task_id, Task.organization_id == actor.organization_id,
            Task.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        on_time_rate, open_load = await self._assignee_stats(actor.organization_id)
        uid = str(t.assigned_user_id) if t.assigned_user_id else None
        result = self._task_delay(t, _now(), on_time_rate.get(uid), open_load.get(uid, 0))
        completeness = 0.5 + (0.25 if t.due_date else 0) + (0.25 if uid in on_time_rate else 0)
        conf = confidence_score(sample_size=open_load.get(uid, 0) + 3,
                                completeness=completeness,
                                signal_strength=abs(result["delay_risk"] - 50) / 50.0,
                                sample_target=10)
        return self._envelope("task_delay", result, conf)

    async def task_delay_predictions(self, actor: User, limit: int = 50) -> dict:
        self._require_manager(actor)
        now = _now()
        on_time_rate, open_load = await self._assignee_stats(actor.organization_id)
        tasks = (await self.db.execute(select(Task).filter(
            Task.organization_id == actor.organization_id, Task.is_deleted == False,
            Task.status.in_(("Todo", "InProgress"))).limit(1000))).scalars().all()
        out = []
        for t in tasks:
            uid = str(t.assigned_user_id) if t.assigned_user_id else None
            out.append(self._task_delay(t, now, on_time_rate.get(uid), open_load.get(uid, 0)))
        out.sort(key=lambda r: r["delay_risk"], reverse=True)
        at_risk = [r for r in out if r["delay_risk"] >= 50]
        return {"model": "task_delay", "model_version": MODEL_REGISTRY["task_delay"]["version"],
                "open_tasks": len(out), "at_risk": len(at_risk),
                "predictions": out[:limit]}

    # ================= NEW: campaign prediction =================
    async def _channel_benchmarks(self, org) -> dict:
        """Historical per-channel delivery/open/click/conversion rates from
        completed campaigns; falls back to industry-ish defaults when sparse."""
        camps = (await self.db.execute(select(Campaign).filter(
            Campaign.organization_id == org, Campaign.is_deleted == False))).scalars().all()
        agg: dict = {}
        for c in camps:
            if (c.sent_count or 0) <= 0:
                continue
            b = agg.setdefault(c.channel, {"sent": 0, "delivered": 0, "opened": 0,
                                           "clicked": 0, "converted": 0, "revenue": 0.0,
                                           "cost": 0.0, "n": 0})
            b["sent"] += c.sent_count
            b["delivered"] += c.delivered_count or 0
            b["opened"] += c.opened_count or 0
            b["clicked"] += c.clicked_count or 0
            b["converted"] += c.converted_count or 0
            b["revenue"] += float(c.revenue or 0)
            b["cost"] += float(c.cost_per_message or 0) * (c.sent_count or 0)
            b["n"] += 1
        defaults = {"Email": (0.97, 0.22, 0.03, 0.012), "SMS": (0.98, 0.30, 0.05, 0.02),
                    "WhatsApp": (0.95, 0.55, 0.08, 0.03), "Call": (0.9, 0.6, 0.0, 0.05)}
        out = {}
        for ch, d in defaults.items():
            b = agg.get(ch)
            if b and b["sent"] >= 50:
                out[ch] = {"delivery": b["delivered"] / b["sent"],
                           "open": (b["opened"] / b["delivered"]) if b["delivered"] else d[1],
                           "click": (b["clicked"] / b["delivered"]) if b["delivered"] else d[2],
                           "conversion": b["converted"] / b["sent"],
                           "sample": b["sent"], "source": "historical"}
            else:
                out[ch] = {"delivery": d[0], "open": d[1], "click": d[2],
                           "conversion": d[3], "sample": (b["sent"] if b else 0),
                           "source": "benchmark"}
        return out

    def _campaign_prediction(self, c: Campaign, bench: dict) -> dict:
        ch = bench.get(c.channel, {"delivery": 0.95, "open": 0.3, "click": 0.03,
                                   "conversion": 0.02, "sample": 0, "source": "benchmark"})
        audience = c.total_recipients or 0
        if audience <= 0 and c.audience_type == "segment":
            audience = 0  # unknown until built
        exp_delivered = round(audience * ch["delivery"])
        exp_opened = round(exp_delivered * ch["open"])
        exp_clicked = round(exp_delivered * ch["click"])
        exp_converted = round(audience * ch["conversion"])
        cost = round(float(c.cost_per_message or 0) * audience, 2)
        # expected revenue: prior avg order value proxy → use campaign.revenue history if any
        aov = (float(c.revenue) / c.converted_count) if (c.converted_count or 0) else 1000.0
        exp_revenue = round(exp_converted * aov, 2)
        roi = round((exp_revenue - cost) / cost * 100, 1) if cost > 0 else None
        return {"campaign_id": str(c.id), "name": c.name, "channel": c.channel,
                "status": c.status, "audience_size": audience,
                "predicted": {"delivered": exp_delivered, "opened": exp_opened,
                              "clicked": exp_clicked, "converted": exp_converted,
                              "revenue": exp_revenue, "cost": cost, "roi_pct": roi},
                "rates": {"delivery": round(ch["delivery"], 3), "open": round(ch["open"], 3),
                          "click": round(ch["click"], 3), "conversion": round(ch["conversion"], 3)},
                "benchmark_source": ch["source"], "benchmark_sample": ch["sample"]}

    async def predict_campaign(self, actor: User, campaign_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        c = (await self.db.execute(select(Campaign).filter(
            Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id,
            Campaign.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        bench = await self._channel_benchmarks(actor.organization_id)
        pred = self._campaign_prediction(c, bench)
        ch = bench.get(c.channel, {})
        conf = confidence_score(sample_size=int(ch.get("sample") or 0),
                                completeness=1.0 if (c.total_recipients or 0) > 0 else 0.4,
                                signal_strength=0.7 if ch.get("source") == "historical" else 0.4,
                                sample_target=200)
        return self._envelope("campaign_response", pred, conf)

    async def campaign_predictions(self, actor: User, limit: int = 50) -> dict:
        self._require_manager(actor)
        bench = await self._channel_benchmarks(actor.organization_id)
        camps = (await self.db.execute(select(Campaign).filter(
            Campaign.organization_id == actor.organization_id, Campaign.is_deleted == False,
            Campaign.status.in_(("draft", "scheduled", "running")))
            .order_by(Campaign.created_at.desc()).limit(1000))).scalars().all()
        out = [self._campaign_prediction(c, bench) for c in camps]
        out.sort(key=lambda r: (r["predicted"]["roi_pct"] or -1e9), reverse=True)
        return {"model": "campaign_response",
                "model_version": MODEL_REGISTRY["campaign_response"]["version"],
                "channel_benchmarks": bench, "count": len(out), "predictions": out[:limit]}

    # ================= forecast accuracy (regression + classification) =======
    async def forecast_accuracy(self, actor: User) -> dict:
        self._require_manager(actor)
        # regression: revenue & sales holdout backtests via ForecastingService
        regression = []
        for metric, model_key in (("revenue", "revenue"), ("sales", "sales_pipeline")):
            bt = await self.forecasting.historical_comparison(actor, metric=metric,
                                                             granularity="monthly")
            regression.append({"model": model_key, "metric": metric, "type": "regression",
                               "mape": bt.get("mape"), "accuracy": bt.get("accuracy"),
                               "note": bt.get("note")})
        # classification: calibrate lead-conversion & churn against known labels.
        # closed leads carry the `converted` label; recompute their predicted
        # probability from features (the pipeline dataset nulls it for closed rows).
        classification = []
        lead_feats = await self.predictive._ds_lead_conversion(actor)
        lead_pairs = []
        for f in lead_feats:
            if f.get("converted") is None:
                continue
            prob, _ = self.predictive._lead_probability(f)
            lead_pairs.append((prob, f["converted"]))
        classification.append(self._classification_accuracy("lead_conversion", lead_pairs))
        churn_rows = await self.predictive._ds_customer_churn(actor)
        classification.append(self._classification_accuracy(
            "customer_churn",
            [(r["churn_risk"], r["churned"]) for r in churn_rows if r["churned"] is not None]))
        graded = [r for r in classification + regression if r.get("accuracy") is not None]
        overall = round(sum(r["accuracy"] for r in graded) / len(graded), 1) if graded else None
        return {"engine_version": ENGINE_VERSION, "overall_accuracy": overall,
                "regression": regression, "classification": classification}

    def _classification_accuracy(self, model_key: str, pairs: list[tuple]) -> dict:
        """Backtest a probability model on labelled history: directional accuracy
        (prob≥50 ⇒ positive) plus a Brier score (mean squared prob error)."""
        pairs = [(p, y) for p, y in pairs if p is not None and y is not None]
        if len(pairs) < 2:
            return {"model": model_key, "type": "classification", "samples": len(pairs),
                    "accuracy": None, "brier": None, "note": "Not enough labelled history."}
        correct = sum(1 for p, y in pairs if (1 if p >= 50 else 0) == y)
        brier = sum(((p / 100.0) - y) ** 2 for p, y in pairs) / len(pairs)
        return {"model": model_key, "type": "classification", "samples": len(pairs),
                "accuracy": round(correct * 100 / len(pairs), 1),
                "brier": round(brier, 3),
                "positive_rate": _rate(sum(y for _, y in pairs), len(pairs))}

    # ================= dashboard / report / export =================
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        sales = await self.predict_sales(actor)
        revenue = await self.predict_revenue(actor, periods=3)
        tasks = await self.task_delay_predictions(actor, limit=5)
        campaigns = await self.campaign_predictions(actor, limit=5)
        churn = await self.predictive._ds_customer_churn(actor)
        at_risk_customers = sorted(churn, key=lambda r: -r["churn_risk"])[:5]
        return {"engine_version": ENGINE_VERSION, "algorithm": ALGORITHM,
                "models_active": len(MODEL_REGISTRY),
                "sales": {"open_deals": sales["open_deals"],
                          "weighted_expected_value": sales["weighted_expected_value"],
                          "win_rate": sales["win_rate"], "confidence": sales["confidence"]},
                "revenue": {"total_forecast": revenue["total_forecast"],
                            "trend": revenue["trend"].get("direction"),
                            "backtest_accuracy": revenue["backtest_accuracy"],
                            "confidence": revenue["confidence"]},
                "tasks": {"open": tasks["open_tasks"], "at_risk": tasks["at_risk"],
                          "top": tasks["predictions"]},
                "campaigns": {"count": campaigns["count"], "top": campaigns["predictions"]},
                "customers_at_risk": [{"customer_id": r["customer_id"],
                                       "customer_name": r["customer_name"],
                                       "churn_risk": r["churn_risk"]} for r in at_risk_customers]}

    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        sales = await self.predict_sales(actor)
        revenue = await self.predict_revenue(actor, periods=6)
        tasks = await self.task_delay_predictions(actor)
        campaigns = await self.campaign_predictions(actor)
        accuracy = await self.forecast_accuracy(actor)
        return {"generated_at": _now().isoformat(), "engine_version": ENGINE_VERSION,
                "models": self.models()["models"],
                "summary": {"open_pipeline_value": sales["open_pipeline_value"],
                            "weighted_expected_value": sales["weighted_expected_value"],
                            "win_rate": sales["win_rate"],
                            "revenue_forecast_6p": revenue["total_forecast"],
                            "tasks_at_risk": tasks["at_risk"],
                            "campaigns_evaluated": campaigns["count"],
                            "overall_accuracy": accuracy["overall_accuracy"]},
                "sales": sales, "revenue": revenue,
                "task_delay": tasks, "campaigns": campaigns, "accuracy": accuracy}

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        rep = await self.report(actor)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["section", "key", "value", "detail"])
        s = rep["summary"]
        for k, v in s.items():
            w.writerow(["summary", k, v, ""])
        for r in rep["accuracy"]["regression"] + rep["accuracy"]["classification"]:
            w.writerow(["accuracy", r["model"], r.get("accuracy"),
                        f"type={r['type']}"])
        for t in rep["task_delay"]["predictions"][:50]:
            w.writerow(["task_delay", t["title"], t["delay_risk"], t["band"]])
        for c in rep["campaigns"]["predictions"][:50]:
            w.writerow(["campaign", c["name"], c["predicted"]["roi_pct"], c["channel"]])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="PREDICTION_REPORT_EXPORTED",
                                   resource_type="prediction_engine",
                                   action_metadata={"engine_version": ENGINE_VERSION})
        await self.db.commit()
        return buf.getvalue()

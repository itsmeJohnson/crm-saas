"""Forecasting Engine — a reusable time-series forecasting layer.

Builds historical series from existing CRM data (invoices, leads, payments,
users, pipeline, targets) and projects them forward with three methods
(moving average, linear trend, seasonal), plus scenario analysis (optimistic /
base / pessimistic), seasonality indices, trend analysis, and a backtested
accuracy check (historical comparison). No new tables — pure computation over
data other modules already own. Org-scoped; managers and admins only.
"""
from __future__ import annotations
import csv
import io
import statistics
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment

METRICS = ("revenue", "sales", "leads", "collections", "staff")
METHODS = ("linear", "moving_average", "seasonal")
GRANULARITIES = ("daily", "weekly", "monthly")
WON_STATUSES = ("Won", "Converted")
DEFAULT_LOOKBACK = {"daily": 45, "weekly": 16, "monthly": 12}  # buckets of history to build


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _f(v) -> float:
    return float(v or 0)


def _bucket_start(d: date, granularity: str) -> date:
    if granularity == "weekly":
        return d - timedelta(days=d.weekday())
    if granularity == "monthly":
        return d.replace(day=1)
    return d


def _bucket_seq(fd: date, td: date, granularity: str) -> list[str]:
    """Continuous, gap-free bucket labels from fd..td."""
    out, cur = [], _bucket_start(fd, granularity)
    end = _bucket_start(td, granularity)
    while cur <= end:
        out.append(cur.isoformat())
        if granularity == "daily":
            cur = cur + timedelta(days=1)
        elif granularity == "weekly":
            cur = cur + timedelta(days=7)
        else:
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def _next_buckets(last: str, periods: int, granularity: str) -> list[str]:
    out, cur = [], date.fromisoformat(last)
    for _ in range(periods):
        if granularity == "daily":
            cur = cur + timedelta(days=1)
        elif granularity == "weekly":
            cur = cur + timedelta(days=7)
        else:
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append(cur.isoformat())
    return out


class ForecastingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="The forecasting engine is available to managers and admins only.")

    def catalog(self) -> dict:
        return {"metrics": list(METRICS), "methods": list(METHODS), "granularities": list(GRANULARITIES)}

    # ================= series builders =================
    async def _series(self, actor: User, metric: str, granularity: str, lookback: int) -> list[dict]:
        if metric not in METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {list(METRICS)}")
        if granularity not in GRANULARITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"granularity must be one of {list(GRANULARITIES)}")
        org = actor.organization_id
        td = date.today()
        span_days = {"daily": lookback, "weekly": lookback * 7, "monthly": lookback * 31}[granularity]
        fd = td - timedelta(days=span_days)
        start = datetime.combine(fd, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(td, time.max).replace(tzinfo=timezone.utc)
        agg: dict = {}

        def add(d: date, v: float):
            k = _bucket_start(d, granularity).isoformat()
            agg[k] = agg.get(k, 0.0) + v

        if metric == "revenue":
            for tot, ca in (await self.db.execute(select(CustomerInvoice.total_amount, CustomerInvoice.created_at).filter(
                    CustomerInvoice.organization_id == org, CustomerInvoice.is_deleted == False,
                    CustomerInvoice.status != "Void", CustomerInvoice.created_at >= start,
                    CustomerInvoice.created_at <= end))).all():
                add(_aware(ca).date(), _f(tot))
        elif metric == "collections":
            for amt, ca in (await self.db.execute(select(CustomerPayment.amount, CustomerPayment.created_at).filter(
                    CustomerPayment.organization_id == org, CustomerPayment.is_deleted == False,
                    CustomerPayment.created_at >= start, CustomerPayment.created_at <= end))).all():
                add(_aware(ca).date(), _f(amt))
        elif metric == "sales":
            for val, conv in (await self.db.execute(select(Lead.value, Lead.converted_at).filter(
                    Lead.organization_id == org, Lead.is_deleted == False, Lead.converted_at.isnot(None),
                    Lead.converted_at >= start, Lead.converted_at <= end))).all():
                add(_aware(conv).date(), _f(val))
        elif metric == "leads":
            for (ca,) in (await self.db.execute(select(Lead.created_at).filter(
                    Lead.organization_id == org, Lead.is_deleted == False,
                    Lead.created_at >= start, Lead.created_at <= end))).all():
                add(_aware(ca).date(), 1)
        elif metric == "staff":
            for (ca,) in (await self.db.execute(select(User.created_at).filter(
                    User.organization_id == org, User.is_deleted == False,
                    User.created_at >= start, User.created_at <= end))).all():
                add(_aware(ca).date(), 1)

        return [{"bucket": b, "value": round(agg.get(b, 0.0), 2)} for b in _bucket_seq(fd, td, granularity)]

    # ================= math =================
    @staticmethod
    def _linear_fit(y: list[float]) -> tuple[float, float]:
        n = len(y)
        if n < 2:
            return 0.0, (y[0] if y else 0.0)
        xs = list(range(n))
        mx, my = sum(xs) / n, sum(y) / n
        var = sum((x - mx) ** 2 for x in xs)
        if var == 0:
            return 0.0, my
        slope = sum((xs[i] - mx) * (y[i] - my) for i in range(n)) / var
        return slope, my - slope * mx

    def _seasonal_idx(self, y: list[float], period: int) -> list[float]:
        if not y or period <= 1:
            return [1.0] * max(1, period)
        overall = sum(y) / len(y) or 1.0
        idx = []
        for p in range(period):
            vals = [y[i] for i in range(len(y)) if i % period == p]
            idx.append(round((sum(vals) / len(vals)) / overall, 3) if vals else 1.0)
        return idx

    def _project(self, y: list[float], periods: int, method: str, granularity: str) -> list[float]:
        n = len(y)
        if n == 0:
            return [0.0] * periods
        if method == "moving_average":
            w = min(3, n)
            avg = sum(y[-w:]) / w
            return [round(max(0.0, avg), 2)] * periods
        slope, intercept = self._linear_fit(y)
        base = [intercept + slope * (n + i) for i in range(periods)]
        if method == "seasonal":
            period = {"daily": 7, "weekly": 4, "monthly": 12}[granularity]
            idx = self._seasonal_idx(y, period)
            base = [base[i] * idx[(n + i) % period] for i in range(periods)]
        return [round(max(0.0, v), 2) for v in base]

    def _residual_std(self, y: list[float]) -> float:
        n = len(y)
        if n < 3:
            return 0.0
        slope, intercept = self._linear_fit(y)
        res = [y[i] - (intercept + slope * i) for i in range(n)]
        try:
            return statistics.pstdev(res)
        except Exception:
            return 0.0

    # ================= public forecasts =================
    async def forecast(self, actor: User, metric="revenue", periods=6, method="linear", granularity="monthly") -> dict:
        self._require_manager(actor)
        if method not in METHODS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"method must be one of {list(METHODS)}")
        periods = max(1, min(periods, 36))
        history = await self._series(actor, metric, granularity, DEFAULT_LOOKBACK[granularity])
        y = [h["value"] for h in history]
        proj = self._project(y, periods, method, granularity)
        band = 1.28 * self._residual_std(y)  # ~80% interval
        last = history[-1]["bucket"] if history else date.today().isoformat()
        fbuckets = _next_buckets(last, periods, granularity)
        forecast = [{"bucket": fbuckets[i], "value": proj[i],
                     "lower": round(max(0.0, proj[i] - band), 2), "upper": round(proj[i] + band, 2)}
                    for i in range(periods)]
        slope, _ = self._linear_fit(y)
        return {"metric": metric, "method": method, "granularity": granularity,
                "history": history, "forecast": forecast,
                "total_forecast": round(sum(proj), 2),
                "history_avg": round(sum(y) / len(y), 2) if y else 0.0,
                "trend": self._trend_of(y)}

    def _trend_of(self, y: list[float]) -> dict:
        slope, _ = self._linear_fit(y)
        first, last = (y[0], y[-1]) if y else (0.0, 0.0)
        growth = round((last - first) / first * 100, 1) if first else 0.0
        direction = "up" if slope > 0.01 else "down" if slope < -0.01 else "flat"
        return {"slope": round(slope, 3), "direction": direction, "growth_rate": growth,
                "avg": round(sum(y) / len(y), 2) if y else 0.0}

    async def scenario_analysis(self, actor: User, metric="revenue", periods=6, method="linear", granularity="monthly") -> dict:
        base = await self.forecast(actor, metric, periods, method, granularity)
        proj = [f["value"] for f in base["forecast"]]
        buckets = [f["bucket"] for f in base["forecast"]]

        def scale(factor):
            return [{"bucket": buckets[i], "value": round(proj[i] * factor, 2)} for i in range(len(proj))]
        return {"metric": metric, "granularity": granularity,
                "scenarios": {
                    "pessimistic": {"factor": 0.85, "series": scale(0.85), "total": round(sum(proj) * 0.85, 2)},
                    "base": {"factor": 1.0, "series": scale(1.0), "total": round(sum(proj), 2)},
                    "optimistic": {"factor": 1.15, "series": scale(1.15), "total": round(sum(proj) * 1.15, 2)},
                }}

    async def seasonality(self, actor: User, metric="revenue", granularity="monthly") -> dict:
        self._require_manager(actor)
        history = await self._series(actor, metric, granularity, DEFAULT_LOOKBACK[granularity])
        y = [h["value"] for h in history]
        period = {"daily": 7, "weekly": 4, "monthly": 12}[granularity]
        idx = self._seasonal_idx(y, period)
        labels = (["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] if granularity == "daily"
                  else [f"W{i+1}" for i in range(period)] if granularity == "weekly"
                  else ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        rows = [{"label": labels[i], "index": idx[i]} for i in range(period)]
        peak = max(rows, key=lambda r: r["index"]) if rows else None
        trough = min(rows, key=lambda r: r["index"]) if rows else None
        return {"metric": metric, "granularity": granularity, "indices": rows, "peak": peak, "trough": trough}

    async def trend_analysis(self, actor: User, metric="revenue", granularity="monthly") -> dict:
        self._require_manager(actor)
        history = await self._series(actor, metric, granularity, DEFAULT_LOOKBACK[granularity])
        y = [h["value"] for h in history]
        return {"metric": metric, "granularity": granularity, "history": history, **self._trend_of(y)}

    async def historical_comparison(self, actor: User, metric="revenue", granularity="monthly", holdout=3) -> dict:
        """Backtest: forecast the last `holdout` buckets from the earlier data and
        compare against what actually happened (accuracy / MAPE)."""
        self._require_manager(actor)
        history = await self._series(actor, metric, granularity, DEFAULT_LOOKBACK[granularity])
        y = [h["value"] for h in history]
        holdout = max(1, min(holdout, max(1, len(y) - 2)))
        if len(y) <= holdout + 1:
            return {"metric": metric, "granularity": granularity, "comparison": [], "mape": None,
                    "accuracy": None, "note": "Not enough history to backtest."}
        train, actual = y[:-holdout], y[-holdout:]
        predicted = self._project(train, holdout, "linear", granularity)
        rows, errs = [], []
        for i in range(holdout):
            a, p = actual[i], predicted[i]
            err = abs(a - p) / a * 100 if a else (0.0 if p == 0 else 100.0)
            errs.append(err)
            rows.append({"bucket": history[len(train) + i]["bucket"], "actual": round(a, 2),
                         "forecast": round(p, 2), "error_pct": round(err, 1)})
        mape = round(sum(errs) / len(errs), 1)
        return {"metric": metric, "granularity": granularity, "comparison": rows,
                "mape": mape, "accuracy": round(max(0.0, 100 - mape), 1)}

    async def pipeline_forecast(self, actor: User, periods=3, granularity="monthly") -> dict:
        """Project pipeline closure: open pipeline value × historical conversion,
        spread over the next periods."""
        self._require_manager(actor)
        org = actor.organization_id
        periods = max(1, min(periods, 12))
        total = (await self.db.execute(select(func.count(Lead.id)).filter(
            Lead.organization_id == org, Lead.is_deleted == False))).scalar() or 0
        won = (await self.db.execute(select(func.count(Lead.id)).filter(
            Lead.organization_id == org, Lead.is_deleted == False, Lead.converted_at.isnot(None)))).scalar() or 0
        conv = round(won * 100 / total, 1) if total else 0.0
        open_value = _f((await self.db.execute(select(func.coalesce(func.sum(Lead.value), 0)).filter(
            Lead.organization_id == org, Lead.is_deleted == False, Lead.converted_at.is_(None),
            Lead.is_archived == False))).scalar())
        expected_close = round(open_value * conv / 100.0, 2)
        per = round(expected_close / periods, 2)
        buckets = _next_buckets(_bucket_start(date.today(), granularity).isoformat(), periods, granularity)
        return {"open_pipeline_value": round(open_value, 2), "conversion_rate": conv,
                "expected_close_total": expected_close, "granularity": granularity,
                "forecast": [{"bucket": b, "value": per} for b in buckets]}

    async def goal_forecast(self, actor: User) -> dict:
        """Project whether active org targets will be met at their run-rate."""
        self._require_manager(actor)
        from app.services.analytics_service import AnalyticsService
        metrics = await AnalyticsService.get_super_admin_metrics(self.db, actor.organization_id, date.today())
        today = date.today()
        rows, on_track = [], 0
        for t in metrics.targets_progress:
            span = (t.end_date - t.start_date).days or 1
            elapsed = max(0, min(span, (today - t.start_date).days))
            frac = elapsed / span if span else 1.0
            projected = round(t.actual_value / frac, 1) if frac > 0 else t.actual_value
            attain = round(projected * 100 / t.target_value, 1) if t.target_value else 0.0
            met = attain >= 100
            on_track += 1 if met else 0
            rows.append({"target_id": str(t.target_id), "metric_type": str(t.metric_type),
                         "target_value": t.target_value, "actual_value": t.actual_value,
                         "progress_pct": t.progress_percentage, "projected_final": projected,
                         "projected_attainment": attain, "on_track": met,
                         "start_date": t.start_date.isoformat(), "end_date": t.end_date.isoformat()})
        return {"targets": rows, "total": len(rows), "on_track": on_track,
                "at_risk": len(rows) - on_track}

    # ================= dashboard / report / export =================
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        out = {}
        for m in ("revenue", "sales", "leads", "collections"):
            f = await self.forecast(actor, m, 1, "linear", "monthly")
            nxt = f["forecast"][0]["value"] if f["forecast"] else 0.0
            out[m] = {"next_month": nxt, "history_avg": f["history_avg"], "direction": f["trend"]["direction"]}
        pipe = await self.pipeline_forecast(actor, 1, "monthly")
        goals = await self.goal_forecast(actor)
        out["pipeline_expected_close"] = pipe["expected_close_total"]
        out["goals_on_track"] = goals["on_track"]
        out["goals_total"] = goals["total"]
        return out

    async def export_csv(self, actor: User, metric="revenue", periods=6, method="linear", granularity="monthly") -> str:
        f = await self.forecast(actor, metric, periods, method, granularity)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([f"{metric} forecast", f"method={method}", f"granularity={granularity}"])
        w.writerow([])
        w.writerow(["Bucket", "Type", "Value", "Lower", "Upper"])
        for h in f["history"]:
            w.writerow([h["bucket"], "actual", h["value"], "", ""])
        for r in f["forecast"]:
            w.writerow([r["bucket"], "forecast", r["value"], r["lower"], r["upper"]])
        return buf.getvalue()

"""Historical Analytics.

A metric time-series warehouse over the whole CRM: every day the cron captures
the KPI engine's cross-domain metric snapshot (~29 org-level metrics — sales,
pipeline, financial, communication, workflow, employee…) into metric_snapshots.
On top of that store: historical trends, month/quarter/year period comparisons,
rolling-window reports, CSV exports and a dashboard. A per-org retention policy
archives daily rows older than the window into monthly averages (Archived Data)
and deletes the dailies. The store is also registered as the `metric_history`
Report Builder dataset, so Report Builder, Visualizations, Scheduled Reports
and the BI feeds can all read it — data-warehouse ready. Existing live
"trend" endpoints in the per-domain analytics services are untouched.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.history import MetricSnapshot, HistorySetting
from app.services.kpi_service import KPIService, METRIC_CATALOG

COMPARISON_PERIODS = ("month", "quarter", "year")
ROLLING_WINDOWS = (7, 30, 90)
KEY_METRICS = ("sales_revenue", "pipeline_value", "mrr", "headcount")  # dashboard sparklines


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _period_window(period: str, ref: date) -> tuple[date, date]:
    """Calendar window containing `ref` for month/quarter/year."""
    import calendar as _cal
    if period == "month":
        return ref.replace(day=1), date(ref.year, ref.month, _cal.monthrange(ref.year, ref.month)[1])
    if period == "quarter":
        q = (ref.month - 1) // 3
        sm, em = q * 3 + 1, q * 3 + 3
        return date(ref.year, sm, 1), date(ref.year, em, _cal.monthrange(ref.year, em)[1])
    return date(ref.year, 1, 1), date(ref.year, 12, 31)


def _previous_ref(period: str, ref: date) -> date:
    """A date inside the previous month/quarter/year."""
    start, _ = _period_window(period, ref)
    return start - timedelta(days=1)


class HistoricalAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Historical analytics is available to managers and admins only.")

    # ---------- meta ----------
    def meta(self) -> dict:
        return {"metrics": [{"key": k, **v} for k, v in METRIC_CATALOG.items() if k != "manual"],
                "comparison_periods": list(COMPARISON_PERIODS), "rolling_windows": list(ROLLING_WINDOWS),
                "key_metrics": list(KEY_METRICS)}

    # ---------- capture (cron + run-now) ----------
    async def capture_org(self, org_id: uuid.UUID, actor: User | None = None) -> dict:
        """Capture today's snapshot of every catalog metric for one org.
        Idempotent per day — re-running updates the same rows."""
        if actor is None:
            actor = (await self.db.execute(select(User).filter(
                User.organization_id == org_id, User.is_deleted == False,
                User.role.in_(["OrgAdmin", "SuperAdmin"])).limit(1))).scalars().first()
            if not actor:
                return {"captured": 0}
        snap = await KPIService(self.db)._snapshot(actor)
        today = _today()
        existing = {r.metric: r for r in (await self.db.execute(select(MetricSnapshot).filter(
            MetricSnapshot.organization_id == org_id, MetricSnapshot.snapshot_date == today,
            MetricSnapshot.granularity == "daily", MetricSnapshot.is_deleted == False))).scalars().all()}
        captured = 0
        for metric in METRIC_CATALOG:
            if metric == "manual":
                continue
            value = snap.get(metric)
            if value is None:
                continue
            row = existing.get(metric)
            if row:
                row.value = _num(value)
                self.db.add(row)
            else:
                self.db.add(MetricSnapshot(organization_id=org_id, snapshot_date=today,
                                           metric=metric, value=_num(value), granularity="daily"))
            captured += 1
        await self.db.flush()
        return {"captured": captured, "date": today.isoformat()}

    async def capture_now(self, actor: User) -> dict:
        self._require_manager(actor)
        return await self.capture_org(actor.organization_id, actor)

    # ---------- retention & archival ----------
    async def _settings_row(self, org_id: uuid.UUID) -> HistorySetting:
        s = (await self.db.execute(select(HistorySetting).filter(
            HistorySetting.organization_id == org_id, HistorySetting.is_deleted == False))).scalars().first()
        if not s:
            s = HistorySetting(organization_id=org_id)
            self.db.add(s)
            await self.db.flush()
        return s

    async def get_settings(self, actor: User) -> dict:
        self._require_manager(actor)
        s = await self._settings_row(actor.organization_id)
        return self._serialize_settings(s)

    async def update_settings(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        s = await self._settings_row(actor.organization_id)
        if data.get("retention_days") is not None:
            days = int(data["retention_days"])
            if days < 30:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="retention_days must be at least 30.")
            s.retention_days = days
        for f in ("archive_enabled", "capture_enabled"):
            if f in data and data[f] is not None:
                setattr(s, f, bool(data[f]))
        self.db.add(s)
        await self.db.flush()
        return self._serialize_settings(s)

    async def apply_retention(self, org_id: uuid.UUID) -> dict:
        """Archive daily rows older than the retention window into monthly
        averages, then delete them. Disabled archiving prunes without archiving."""
        s = await self._settings_row(org_id)
        cutoff = _today() - timedelta(days=s.retention_days)
        old = (await self.db.execute(select(MetricSnapshot).filter(
            MetricSnapshot.organization_id == org_id, MetricSnapshot.granularity == "daily",
            MetricSnapshot.is_deleted == False, MetricSnapshot.snapshot_date < cutoff))).scalars().all()
        if not old:
            return {"archived_months": 0, "pruned": 0}
        archived = 0
        if s.archive_enabled:
            buckets: dict[tuple, list[float]] = {}
            for r in old:
                key = (r.snapshot_date.replace(day=1), r.metric)
                buckets.setdefault(key, []).append(_num(r.value))
            for (month_start, metric), values in buckets.items():
                existing = (await self.db.execute(select(MetricSnapshot).filter(
                    MetricSnapshot.organization_id == org_id, MetricSnapshot.snapshot_date == month_start,
                    MetricSnapshot.metric == metric, MetricSnapshot.granularity == "monthly",
                    MetricSnapshot.is_deleted == False))).scalars().first()
                avg = round(sum(values) / len(values), 2)
                if existing:
                    existing.value = avg
                    self.db.add(existing)
                else:
                    self.db.add(MetricSnapshot(organization_id=org_id, snapshot_date=month_start,
                                               metric=metric, value=avg, granularity="monthly"))
                    archived += 1
        ids = [r.id for r in old]
        await self.db.execute(sa_delete(MetricSnapshot).where(MetricSnapshot.id.in_(ids)))
        await self.db.flush()
        return {"archived_months": archived, "pruned": len(ids)}

    # ---------- queries ----------
    async def _series(self, org_id: uuid.UUID, metric: str, start: date, end: date) -> list[dict]:
        rows = (await self.db.execute(select(MetricSnapshot).filter(
            MetricSnapshot.organization_id == org_id, MetricSnapshot.metric == metric,
            MetricSnapshot.is_deleted == False, MetricSnapshot.snapshot_date >= start,
            MetricSnapshot.snapshot_date <= end)
            .order_by(MetricSnapshot.snapshot_date.asc()))).scalars().all()
        return [{"date": r.snapshot_date.isoformat(), "value": _num(r.value),
                 "granularity": r.granularity} for r in rows]

    def _check_metric(self, metric: str):
        if metric not in METRIC_CATALOG or metric == "manual":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown metric '{metric}'.")

    async def trends(self, actor: User, metric: str, days: int = 90) -> dict:
        self._require_manager(actor)
        self._check_metric(metric)
        days = max(7, min(int(days), 1460))
        start = _today() - timedelta(days=days)
        points = await self._series(actor.organization_id, metric, start, _today())
        values = [p["value"] for p in points]
        change_pct = None
        if len(values) >= 2 and values[0]:
            change_pct = round((values[-1] - values[0]) * 100 / abs(values[0]), 1)
        return {"metric": metric, "label": METRIC_CATALOG[metric]["label"],
                "unit": METRIC_CATALOG[metric]["unit"], "days": days, "points": points,
                "latest": values[-1] if values else None,
                "min": min(values) if values else None, "max": max(values) if values else None,
                "change_pct": change_pct}

    async def _period_avgs(self, org_id: uuid.UUID, start: date, end: date) -> dict[str, float]:
        rows = (await self.db.execute(
            select(MetricSnapshot.metric, func.avg(MetricSnapshot.value)).filter(
                MetricSnapshot.organization_id == org_id, MetricSnapshot.is_deleted == False,
                MetricSnapshot.snapshot_date >= start, MetricSnapshot.snapshot_date <= end)
            .group_by(MetricSnapshot.metric))).all()
        return {m: _num(v) for m, v in rows}

    async def comparison(self, actor: User, period: str = "month") -> dict:
        """Monthly / quarterly / yearly comparison: average of each metric's
        snapshots in the current calendar period vs the previous one."""
        self._require_manager(actor)
        if period not in COMPARISON_PERIODS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"period must be one of {list(COMPARISON_PERIODS)}")
        today = _today()
        cur_start, cur_end = _period_window(period, today)
        prev_ref = _previous_ref(period, today)
        prev_start, prev_end = _period_window(period, prev_ref)
        cur = await self._period_avgs(actor.organization_id, cur_start, cur_end)
        prev = await self._period_avgs(actor.organization_id, prev_start, prev_end)
        rows = []
        for metric, meta in METRIC_CATALOG.items():
            if metric == "manual" or (metric not in cur and metric not in prev):
                continue
            c, p = round(cur.get(metric, 0.0), 2), round(prev.get(metric, 0.0), 2)
            change = round(c - p, 2)
            change_pct = round(change * 100 / abs(p), 1) if p else (100.0 if c else 0.0)
            rows.append({"metric": metric, "label": meta["label"], "unit": meta["unit"],
                         "comparison": meta["comparison"], "current": c, "previous": p,
                         "change": change, "change_pct": change_pct,
                         "improved": (change >= 0) == (meta["comparison"] == "higher_better") if change != 0 else None})
        rows.sort(key=lambda r: -abs(r["change_pct"]))
        return {"period": period,
                "current_window": {"start": cur_start.isoformat(), "end": cur_end.isoformat()},
                "previous_window": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
                "rows": rows}

    async def rolling(self, actor: User, metric: str, window: int = 30, days: int = 180) -> dict:
        """Rolling report: the raw daily series plus its rolling-window mean."""
        self._require_manager(actor)
        self._check_metric(metric)
        if int(window) not in ROLLING_WINDOWS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"window must be one of {list(ROLLING_WINDOWS)}")
        window = int(window)
        start = _today() - timedelta(days=max(7, min(int(days), 1460)) + window)
        points = await self._series(actor.organization_id, metric, start, _today())
        out = []
        values: list[float] = []
        for p in points:
            values.append(p["value"])
            tail = values[-window:]
            out.append({**p, "rolling_avg": round(sum(tail) / len(tail), 2)})
        return {"metric": metric, "label": METRIC_CATALOG[metric]["label"],
                "unit": METRIC_CATALOG[metric]["unit"], "window": window, "points": out[-(int(days)):]}

    async def snapshots(self, actor: User, snapshot_date: str | None = None, metric: str | None = None,
                        granularity: str | None = None, limit: int = 200) -> list[dict]:
        self._require_manager(actor)
        q = select(MetricSnapshot).filter(MetricSnapshot.organization_id == actor.organization_id,
                                          MetricSnapshot.is_deleted == False)
        if snapshot_date:
            q = q.filter(MetricSnapshot.snapshot_date == date.fromisoformat(snapshot_date))
        if metric:
            self._check_metric(metric)
            q = q.filter(MetricSnapshot.metric == metric)
        if granularity:
            q = q.filter(MetricSnapshot.granularity == granularity)
        rows = (await self.db.execute(q.order_by(MetricSnapshot.snapshot_date.desc(),
                                                 MetricSnapshot.metric.asc())
                                      .limit(min(limit, 500)))).scalars().all()
        return [{"id": str(r.id), "date": r.snapshot_date.isoformat(), "metric": r.metric,
                 "label": METRIC_CATALOG.get(r.metric, {}).get("label", r.metric),
                 "value": _num(r.value), "granularity": r.granularity} for r in rows]

    # ---------- dashboard & report ----------
    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        days_covered = (await self.db.execute(select(func.count(func.distinct(MetricSnapshot.snapshot_date))).filter(
            MetricSnapshot.organization_id == org, MetricSnapshot.is_deleted == False,
            MetricSnapshot.granularity == "daily"))).scalar() or 0
        metrics_tracked = (await self.db.execute(select(func.count(func.distinct(MetricSnapshot.metric))).filter(
            MetricSnapshot.organization_id == org, MetricSnapshot.is_deleted == False))).scalar() or 0
        archived = (await self.db.execute(select(func.count(MetricSnapshot.id)).filter(
            MetricSnapshot.organization_id == org, MetricSnapshot.is_deleted == False,
            MetricSnapshot.granularity == "monthly"))).scalar() or 0
        last_date = (await self.db.execute(select(func.max(MetricSnapshot.snapshot_date)).filter(
            MetricSnapshot.organization_id == org, MetricSnapshot.is_deleted == False))).scalar()
        comp = await self.comparison(actor, "month")
        movers = [r for r in comp["rows"] if r["previous"] or r["current"]][:5]
        sparklines = {}
        start = _today() - timedelta(days=30)
        for m in KEY_METRICS:
            sparklines[m] = {"label": METRIC_CATALOG[m]["label"], "unit": METRIC_CATALOG[m]["unit"],
                             "points": await self._series(org, m, start, _today())}
        s = await self._settings_row(org)
        return {"days_covered": days_covered, "metrics_tracked": metrics_tracked,
                "archived_rows": archived,
                "last_capture": last_date.isoformat() if last_date else None,
                "top_movers": movers, "sparklines": sparklines,
                "settings": self._serialize_settings(s)}

    async def report(self, actor: User, period: str = "month") -> dict:
        comp = await self.comparison(actor, period)
        improved = sum(1 for r in comp["rows"] if r["improved"] is True)
        declined = sum(1 for r in comp["rows"] if r["improved"] is False)
        return {**comp, "improved": improved, "declined": declined,
                "flat": len(comp["rows"]) - improved - declined}

    # ---------- exports ----------
    async def export_csv(self, actor: User, kind: str = "comparison", metric: str | None = None,
                         period: str = "month", days: int = 90) -> str:
        self._require_manager(actor)
        buf = io.StringIO()
        w = csv.writer(buf)
        if kind == "trend":
            t = await self.trends(actor, metric or "sales_revenue", days=days)
            w.writerow(["date", "metric", "value", "granularity"])
            for p in t["points"]:
                w.writerow([p["date"], t["metric"], p["value"], p["granularity"]])
        elif kind == "snapshots":
            rows = await self.snapshots(actor, limit=500)
            w.writerow(["date", "metric", "value", "granularity"])
            for r in rows:
                w.writerow([r["date"], r["metric"], r["value"], r["granularity"]])
        else:
            comp = await self.comparison(actor, period)
            w.writerow(["metric", "label", "current", "previous", "change", "change_pct"])
            for r in comp["rows"]:
                w.writerow([r["metric"], r["label"], r["current"], r["previous"], r["change"], r["change_pct"]])
        return buf.getvalue()

    # ---------- serialize ----------
    @staticmethod
    def _serialize_settings(s: HistorySetting) -> dict:
        return {"retention_days": s.retention_days, "archive_enabled": s.archive_enabled,
                "capture_enabled": s.capture_enabled}

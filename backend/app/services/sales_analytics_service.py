"""Sales Analytics — sales-specific analytics over the lead pipeline.

Complements the existing lead report (LeadService.get_lead_report) and the sales
role dashboards (AnalyticsService) with the genuinely-missing sales metrics: an
ordered sales/lead funnel with drop-off, win rate, average deal size, sales
velocity and cycle length, lead-source ROI, lost-reason analysis, performance
trends, a weighted forecast and a lead activity heatmap. Org-scoped, and
downline-scoped for managers. No new analytics tables — computed from leads.
"""
from __future__ import annotations
import csv
import io
import statistics
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage

MAX_LEADS = 50000
GRANULARITIES = ("daily", "weekly", "monthly")
WON_STATUSES = ("Won", "Converted")
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _val(lead: Lead) -> float:
    return float(lead.value or 0)


class SalesAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / scope / window ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Sales analytics are available to managers and admins only.")

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

    def _window(self, date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
        today = date.today()
        to_d = date_to or today
        from_d = date_from or (to_d - timedelta(days=89))
        return (datetime.combine(from_d, time.min).replace(tzinfo=timezone.utc),
                datetime.combine(to_d, time.max).replace(tzinfo=timezone.utc))

    # ---------- classifiers ----------
    @staticmethod
    def _is_won(l: Lead) -> bool:
        return l.converted_at is not None or l.status in WON_STATUSES

    @staticmethod
    def _is_lost(l: Lead) -> bool:
        return l.status == "Lost"

    def _is_open(self, l: Lead) -> bool:
        return not self._is_won(l) and not self._is_lost(l) and not getattr(l, "is_archived", False)

    @staticmethod
    def _rate(part, whole) -> float:
        return round(part * 100 / whole, 1) if whole else 0.0

    # ---------- fetch ----------
    async def _fetch(self, actor: User, start: datetime, end: datetime) -> tuple[list[Lead], list[PipelineStage]]:
        q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
                                Lead.created_at >= start, Lead.created_at <= end)
        scope = await self._scope_ids(actor)
        if scope is not None:
            q = q.filter(Lead.assigned_user_id.in_(list(scope)))
        leads = list((await self.db.execute(q.limit(MAX_LEADS))).scalars().all())
        stages = list((await self.db.execute(select(PipelineStage).filter(
            PipelineStage.organization_id == actor.organization_id, PipelineStage.is_deleted == False)
            .order_by(PipelineStage.order_position.asc()))).scalars().all())
        return leads, stages

    def _cycle_days(self, leads: list[Lead]) -> list[float]:
        out = []
        for l in leads:
            if l.converted_at and l.created_at:
                d = (_aware(l.converted_at) - _aware(l.created_at)).total_seconds() / 86400
                if d >= 0:
                    out.append(round(d, 2))
        return out

    # ================= public surface =================
    async def overview(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        won = [l for l in leads if self._is_won(l)]
        lost = [l for l in leads if self._is_lost(l)]
        open_ = [l for l in leads if self._is_open(l)]
        won_value = sum(_val(l) for l in won)
        cycles = self._cycle_days(won)
        avg_cycle = round(sum(cycles) / len(cycles), 1) if cycles else 0.0
        avg_deal = round(won_value / len(won), 2) if won else 0.0
        win_rate = self._rate(len(won), len(won) + len(lost))
        conv_rate = self._rate(len(won), len(leads))
        velocity = round((len(open_) * (win_rate / 100) * avg_deal) / avg_cycle, 2) if avg_cycle else 0.0
        return {
            "from": start.date().isoformat(), "to": end.date().isoformat(),
            "total_leads": len(leads), "won": len(won), "lost": len(lost), "open": len(open_),
            "pipeline_value": round(sum(_val(l) for l in open_), 2), "revenue": round(won_value, 2),
            "conversion_rate": conv_rate, "win_rate": win_rate, "avg_deal_size": avg_deal,
            "avg_sales_cycle_days": avg_cycle, "sales_velocity": velocity,
        }

    async def funnel(self, actor: User, date_from=None, date_to=None) -> dict:
        """Lead funnel (by status) + sales funnel (by ordered pipeline stage) with
        stage-to-stage drop-off."""
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, stages = await self._fetch(actor, start, end)
        # sales funnel: leads currently at each ordered stage
        by_stage_id: dict = {}
        for l in leads:
            by_stage_id.setdefault(l.stage_id, []).append(l)
        sales_funnel = []
        prev = None
        for s in stages:
            group = by_stage_id.get(s.id, [])
            cnt = len(group)
            drop = round((prev - cnt) * 100 / prev, 1) if prev else 0.0
            sales_funnel.append({"stage": s.name, "count": cnt, "value": round(sum(_val(l) for l in group), 2),
                                 "drop_off_pct": drop if prev else 0.0})
            prev = cnt if cnt else prev
        # lead funnel: canonical status progression
        order = ["New", "Contacted", "Qualified", "Converted"]
        by_status: dict = {}
        for l in leads:
            by_status[l.status] = by_status.get(l.status, 0) + 1
        lead_funnel = [{"status": st, "count": by_status.get(st, 0)} for st in order]
        # append any non-canonical statuses (Lost, Won, custom)
        for st, n in sorted(by_status.items(), key=lambda kv: -kv[1]):
            if st not in order:
                lead_funnel.append({"status": st, "count": n})
        return {"sales_funnel": sales_funnel, "lead_funnel": lead_funnel, "total": len(leads)}

    async def conversion(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        won = [l for l in leads if self._is_won(l)]
        by_source: dict = {}
        for l in leads:
            src = l.source or "Unspecified"
            b = by_source.setdefault(src, {"leads": 0, "won": 0})
            b["leads"] += 1
            if self._is_won(l):
                b["won"] += 1
        rows = [{"source": k, "leads": v["leads"], "won": v["won"], "conversion_rate": self._rate(v["won"], v["leads"])}
                for k, v in sorted(by_source.items(), key=lambda kv: -kv[1]["leads"])]
        return {"conversion_rate": self._rate(len(won), len(leads)), "total_leads": len(leads),
                "won": len(won), "by_source": rows}

    async def revenue(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        won = [l for l in leads if self._is_won(l)]
        won_value = sum(_val(l) for l in won)
        by_source: dict = {}
        for l in won:
            by_source[l.source or "Unspecified"] = by_source.get(l.source or "Unspecified", 0.0) + _val(l)
        return {"revenue": round(won_value, 2), "won_deals": len(won),
                "avg_deal_size": round(won_value / len(won), 2) if won else 0.0,
                "by_source": [{"source": k, "revenue": round(v, 2)} for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])]}

    async def source_roi(self, actor: User, date_from=None, date_to=None) -> dict:
        """Lead source ROI: per source — leads, won, revenue, conversion, value per
        lead and average deal size (the return signal per source of leads)."""
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        by_source: dict = {}
        for l in leads:
            src = l.source or "Unspecified"
            b = by_source.setdefault(src, {"leads": 0, "won": 0, "revenue": 0.0})
            b["leads"] += 1
            if self._is_won(l):
                b["won"] += 1
                b["revenue"] += _val(l)
        rows = []
        for src, v in by_source.items():
            rows.append({"source": src, "leads": v["leads"], "won": v["won"], "revenue": round(v["revenue"], 2),
                         "conversion_rate": self._rate(v["won"], v["leads"]),
                         "value_per_lead": round(v["revenue"] / v["leads"], 2) if v["leads"] else 0.0,
                         "avg_deal_size": round(v["revenue"] / v["won"], 2) if v["won"] else 0.0})
        rows.sort(key=lambda r: -r["revenue"])
        return {"sources": rows}

    async def lost_reasons(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        lost = [l for l in leads if self._is_lost(l)]
        by_reason: dict = {}
        for l in lost:
            r = (l.lost_reason or "Unspecified").strip() or "Unspecified"
            b = by_reason.setdefault(r, {"count": 0, "value": 0.0})
            b["count"] += 1
            b["value"] += _val(l)
        rows = [{"reason": k, "count": v["count"], "lost_value": round(v["value"], 2),
                 "share_pct": self._rate(v["count"], len(lost))}
                for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1]["count"])]
        return {"total_lost": len(lost), "lost_value": round(sum(_val(l) for l in lost), 2), "by_reason": rows}

    async def velocity_and_cycle(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        won = [l for l in leads if self._is_won(l)]
        lost = [l for l in leads if self._is_lost(l)]
        open_ = [l for l in leads if self._is_open(l)]
        cycles = self._cycle_days(won)
        avg_cycle = round(sum(cycles) / len(cycles), 1) if cycles else 0.0
        won_value = sum(_val(l) for l in won)
        avg_deal = round(won_value / len(won), 2) if won else 0.0
        win_rate = self._rate(len(won), len(won) + len(lost))
        velocity = round((len(open_) * (win_rate / 100) * avg_deal) / avg_cycle, 2) if avg_cycle else 0.0
        return {
            "win_rate": win_rate, "opportunities": len(open_), "avg_deal_size": avg_deal,
            "avg_sales_cycle_days": avg_cycle,
            "median_cycle_days": round(statistics.median(cycles), 1) if cycles else 0.0,
            "min_cycle_days": round(min(cycles), 1) if cycles else 0.0,
            "max_cycle_days": round(max(cycles), 1) if cycles else 0.0,
            "sales_velocity": velocity,
            "velocity_note": "(opportunities × win_rate × avg_deal_size) ÷ avg_cycle_days per day",
        }

    async def forecast(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        won = [l for l in leads if self._is_won(l)]
        open_ = [l for l in leads if self._is_open(l)]
        conv = self._rate(len(won), len(leads))
        realised = sum(_val(l) for l in won)
        open_value = sum(_val(l) for l in open_)
        weighted = round(open_value * conv / 100.0, 2)
        return {"open_pipeline_value": round(open_value, 2), "conversion_rate": conv,
                "weighted_pipeline": weighted, "realised_revenue": round(realised, 2),
                "projected_total": round(realised + weighted, 2), "open_deals": len(open_)}

    async def trend(self, actor: User, granularity: str = "monthly", date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        if granularity not in GRANULARITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"granularity must be one of {list(GRANULARITIES)}")
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)

        def bucket(dt: datetime) -> str:
            d = _aware(dt).date()
            if granularity == "daily":
                return d.isoformat()
            if granularity == "weekly":
                return (d - timedelta(days=d.weekday())).isoformat()
            return d.replace(day=1).isoformat()

        buckets: dict = {}
        for l in leads:
            b = buckets.setdefault(bucket(l.created_at), {"leads": 0, "won": 0, "lost": 0, "revenue": 0.0})
            b["leads"] += 1
            if self._is_won(l):
                b["won"] += 1
                b["revenue"] += _val(l)
            elif self._is_lost(l):
                b["lost"] += 1
        series = [{"bucket": k, "leads": v["leads"], "won": v["won"], "lost": v["lost"],
                   "revenue": round(v["revenue"], 2), "win_rate": self._rate(v["won"], v["won"] + v["lost"])}
                  for k, v in sorted(buckets.items())]
        return {"granularity": granularity, "from": start.date().isoformat(), "to": end.date().isoformat(), "series": series}

    async def heatmap(self, actor: User, date_from=None, date_to=None) -> dict:
        """Lead creation heatmap (weekday × hour) + a won-lead overlay + peak."""
        self._require_manager(actor)
        start, end = self._window(date_from, date_to)
        leads, _ = await self._fetch(actor, start, end)
        grid = [[0] * 24 for _ in range(7)]
        won_grid = [[0] * 24 for _ in range(7)]
        peak = {"weekday": 0, "hour": 0, "count": 0}
        for l in leads:
            if not l.created_at:
                continue
            dt = _aware(l.created_at)
            wd, hr = dt.weekday(), dt.hour
            grid[wd][hr] += 1
            if self._is_won(l):
                won_grid[wd][hr] += 1
            if grid[wd][hr] > peak["count"]:
                peak = {"weekday": wd, "hour": hr, "count": grid[wd][hr]}
        peak["weekday_label"] = WEEKDAYS[peak["weekday"]]
        return {"weekdays": WEEKDAYS, "grid": grid, "won_grid": won_grid, "peak": peak}

    async def dashboard(self, actor: User) -> dict:
        """Compact headline set for the Home widget (trailing 90 days)."""
        ov = await self.overview(actor, None, None)
        return {"revenue": ov["revenue"], "win_rate": ov["win_rate"], "conversion_rate": ov["conversion_rate"],
                "avg_deal_size": ov["avg_deal_size"], "sales_velocity": ov["sales_velocity"],
                "pipeline_value": ov["pipeline_value"], "won": ov["won"], "open": ov["open"]}

    async def export_csv(self, actor: User, date_from=None, date_to=None) -> str:
        ov = await self.overview(actor, date_from, date_to)
        src = await self.source_roi(actor, date_from, date_to)
        lost = await self.lost_reasons(actor, date_from, date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Sales analytics", f"{ov['from']} → {ov['to']}"])
        w.writerow([])
        w.writerow(["Metric", "Value"])
        for k in ("total_leads", "won", "lost", "open", "revenue", "pipeline_value", "conversion_rate",
                  "win_rate", "avg_deal_size", "avg_sales_cycle_days", "sales_velocity"):
            w.writerow([k, ov[k]])
        w.writerow([])
        w.writerow(["Source", "Leads", "Won", "Revenue", "Conversion %", "Value/lead"])
        for s in src["sources"]:
            w.writerow([s["source"], s["leads"], s["won"], s["revenue"], s["conversion_rate"], s["value_per_lead"]])
        w.writerow([])
        w.writerow(["Lost reason", "Count", "Lost value", "Share %"])
        for r in lost["by_reason"]:
            w.writerow([r["reason"], r["count"], r["lost_value"], r["share_pct"]])
        return buf.getvalue()

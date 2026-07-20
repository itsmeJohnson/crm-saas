"""Data Visualization.

A chart-first layer over the Custom Report Builder's safe query engine: every
visualization (bar/line/area/pie, table, pivot, heatmap, treemap, funnel, gauge,
timeline, comparison, geo) is rendered on demand from a viz spec — dataset +
config + rule-engine filters — by delegating row fetching/grouping/pivoting to
ReportBuilderService.run_definition and shaping the result per type in Python.
Saved visualizations live in the `visualizations` table and can be pinned to the
Home dashboard; drill-down returns the underlying rows behind any datum. No
domain events, no cron. The Report Builder and per-module analytics pages are
untouched.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import date, datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.visualization import Visualization
from app.services.report_builder_service import ReportBuilderService, MAX_ROWS, AGGREGATIONS

VIZ_TYPES = ("bar", "line", "area", "pie", "table", "pivot", "heatmap", "treemap",
             "funnel", "gauge", "timeline", "comparison", "geo")
INTERVALS = ("day", "week", "month")
VISIBILITIES = ("private", "organization")

# Indian postal zones by PIN first digit — used to coarsen pin_code geo fields.
PIN_ZONES = {
    "1": "North (Delhi, Haryana, Punjab, HP, J&K)",
    "2": "UP & Uttarakhand",
    "3": "Rajasthan & Gujarat",
    "4": "Maharashtra, MP & Goa",
    "5": "AP, Telangana & Karnataka",
    "6": "Tamil Nadu & Kerala",
    "7": "WB, Odisha & North-East",
    "8": "Bihar & Jharkhand",
    "9": "Army Postal",
}

VIZ_META = {
    "bar":        {"label": "Bar chart",     "needs": ["dimension"], "optional": ["measure"]},
    "line":       {"label": "Line chart",    "needs": ["dimension"], "optional": ["measure"]},
    "area":       {"label": "Area chart",    "needs": ["dimension"], "optional": ["measure"]},
    "pie":        {"label": "Pie chart",     "needs": ["dimension"], "optional": ["measure"]},
    "table":      {"label": "Table",         "needs": [], "optional": ["columns"]},
    "pivot":      {"label": "Pivot table",   "needs": ["row", "col"], "optional": ["measure"]},
    "heatmap":    {"label": "Heatmap",       "needs": ["row", "col"], "optional": ["measure"]},
    "treemap":    {"label": "Treemap",       "needs": ["dimension"], "optional": ["measure"]},
    "funnel":     {"label": "Funnel",        "needs": ["dimension"], "optional": ["stages"]},
    "gauge":      {"label": "Gauge",         "needs": ["target"], "optional": ["measure"]},
    "timeline":   {"label": "Timeline",      "needs": ["date_field"], "optional": ["interval", "measure"]},
    "comparison": {"label": "Comparison",    "needs": ["date_field"], "optional": ["window_days", "dimension", "measure"]},
    "geo":        {"label": "Geo map",       "needs": ["field"], "optional": []},
}


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _cond(field: str, op: str, value) -> dict:
    return {"type": "condition", "field": field, "op": op, "value": value}


def _and(*children) -> dict:
    return {"type": "group", "logic": "and", "children": [c for c in children if c]}


def _merge_filters(base, extra: dict | None):
    """AND an extra condition group onto whatever filter the spec already has."""
    if not extra:
        return base
    if not base:
        return extra
    return {"type": "group", "logic": "and", "children": [base, extra]}


class VisualizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rb = ReportBuilderService(db)

    # ---------- catalog ----------
    def catalog(self) -> dict:
        rb_cat = self.rb.catalog()
        return {"viz_types": [{"key": k, **m} for k, m in VIZ_META.items()],
                "datasets": rb_cat["datasets"], "aggregations": list(AGGREGATIONS),
                "intervals": list(INTERVALS), "visibilities": list(VISIBILITIES),
                "operators": rb_cat["operators"], "logic": rb_cat["logic"]}

    # ---------- engine helpers (delegate to the report builder) ----------
    def _measure(self, config: dict) -> tuple[str, list, str]:
        """Returns (value_key, measure_columns, label) for a config measure."""
        m = config.get("measure") or {}
        agg, field = (m.get("agg") or "count"), m.get("field")
        if agg not in AGGREGATIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"agg must be one of {list(AGGREGATIONS)}")
        if not field or agg == "count":
            return "count", [], "count"
        return f"{agg}__{field}", [{"field": field, "agg": agg}], f"{agg}({field})"

    async def _grouped(self, actor: User, dataset: str, dimension: str, config: dict, filters) -> tuple[list, str]:
        key, cols, label = self._measure(config)
        res = await self.rb.run_definition(actor, {"dataset": dataset, "columns": cols,
                                                   "group_by": [dimension], "filters": filters},
                                           limit=MAX_ROWS)
        points = [{"label": str(r.get(dimension)) if r.get(dimension) is not None else "—",
                   "value": _num(r.get(key))} for r in res["rows"]]
        return points, label

    async def _raw(self, actor: User, dataset: str, fields: list[str], filters) -> list[dict]:
        cols = [{"field": f} for f in dict.fromkeys(f for f in fields if f)]
        res = await self.rb.run_definition(actor, {"dataset": dataset, "columns": cols, "filters": filters},
                                           limit=MAX_ROWS)
        return res["rows"]

    # ---------- render ----------
    async def render(self, actor: User, spec: dict) -> dict:
        viz_type = spec.get("viz_type")
        if viz_type not in VIZ_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"viz_type must be one of {list(VIZ_TYPES)}")
        dataset = spec.get("dataset")
        config = spec.get("config") or {}
        filters = spec.get("filters")
        handler = getattr(self, f"_render_{viz_type}")
        data = await handler(actor, dataset, config, filters)
        return {"viz_type": viz_type, "dataset": dataset, "config": config, "data": data}

    def _need(self, config: dict, key: str):
        v = config.get(key)
        if not v:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"config.{key} is required for this visualization.")
        return v

    async def _cartesian(self, actor, dataset, config, filters, *, sort_desc: bool, cap: int):
        points, label = await self._grouped(actor, dataset, self._need(config, "dimension"), config, filters)
        if sort_desc:
            points.sort(key=lambda p: -p["value"])
        else:
            points.sort(key=lambda p: p["label"])
        total = round(sum(p["value"] for p in points), 2)
        points = points[:cap]
        return {"points": points, "dimension": config["dimension"], "measure_label": label, "total": total}

    async def _render_bar(self, actor, dataset, config, filters):
        return await self._cartesian(actor, dataset, config, filters, sort_desc=True, cap=25)

    async def _render_pie(self, actor, dataset, config, filters):
        return await self._cartesian(actor, dataset, config, filters, sort_desc=True, cap=12)

    async def _render_treemap(self, actor, dataset, config, filters):
        d = await self._cartesian(actor, dataset, config, filters, sort_desc=True, cap=40)
        return {"nodes": [{"name": p["label"], "value": p["value"]} for p in d["points"] if p["value"] > 0],
                "measure_label": d["measure_label"], "total": d["total"]}

    async def _render_line(self, actor, dataset, config, filters):
        return await self._cartesian(actor, dataset, config, filters, sort_desc=False, cap=100)

    async def _render_area(self, actor, dataset, config, filters):
        return await self._cartesian(actor, dataset, config, filters, sort_desc=False, cap=100)

    async def _render_table(self, actor, dataset, config, filters):
        cols = config.get("columns")
        if not cols:
            ds = self.rb._dataset(dataset)
            cols = [c["field"] for c in ds["columns"]][:8]
        res = await self.rb.run_definition(actor, {"dataset": dataset, "columns": [{"field": c} for c in cols],
                                                   "filters": filters, "sort": config.get("sort") or []},
                                           limit=int(config.get("limit") or 100))
        return {"columns": res["columns"], "rows": res["rows"], "total": res["total"]}

    async def _render_pivot(self, actor, dataset, config, filters):
        pv = {"row": self._need(config, "row"), "col": self._need(config, "col"),
              "measure": (config.get("measure") or {}).get("field"),
              "agg": (config.get("measure") or {}).get("agg") or "count"}
        res = await self.rb.run_definition(actor, {"dataset": dataset, "columns": [], "filters": filters,
                                                   "pivot": pv}, limit=1)
        return res["pivot"]

    async def _render_heatmap(self, actor, dataset, config, filters):
        pivot = await self._render_pivot(actor, dataset, config, filters)
        rows = [str(r["__row"]) if r["__row"] is not None else "—" for r in pivot["rows"]]
        cols = pivot["columns"]
        cells = [[_num(r.get(c)) for c in cols] for r in pivot["rows"]]
        mx = max((v for row in cells for v in row), default=0)
        return {"rows": rows, "cols": cols, "cells": cells, "max": mx, "agg": pivot["agg"]}

    async def _render_funnel(self, actor, dataset, config, filters):
        points, label = await self._grouped(actor, dataset, self._need(config, "dimension"), config, filters)
        by_label = {p["label"]: p["value"] for p in points}
        stages = config.get("stages")
        ordered = ([{"label": s, "value": by_label.get(s, 0)} for s in stages] if stages
                   else sorted(points, key=lambda p: -p["value"]))
        first = ordered[0]["value"] if ordered else 0
        out = []
        prev = None
        for st in ordered:
            pct = round(st["value"] * 100 / first, 1) if first else 0.0
            drop = round((prev - st["value"]) * 100 / prev, 1) if prev not in (None, 0) else 0.0
            out.append({**st, "pct_of_first": pct, "drop_pct": max(0.0, drop)})
            prev = st["value"]
        return {"stages": out, "measure_label": label}

    async def _render_gauge(self, actor, dataset, config, filters):
        target = _num(self._need(config, "target"))
        m = config.get("measure") or {}
        field, agg = m.get("field"), (m.get("agg") or "count")
        rows = await self._raw(actor, dataset, [field] if field else [], filters)
        if not field or agg == "count":
            value = float(len(rows))
        else:
            value = _num(self.rb._aggregate(agg, [r.get(field) for r in rows]))
        pct = round(value * 100 / target, 1) if target else 0.0
        return {"value": round(value, 2), "target": target, "pct": pct,
                "measure_label": "count" if not field or agg == "count" else f"{agg}({field})"}

    @staticmethod
    def _bucket(iso: str, interval: str) -> str | None:
        if not iso:
            return None
        try:
            d = date.fromisoformat(str(iso)[:10])
        except ValueError:
            return None
        if interval == "month":
            return f"{d.year}-{d.month:02d}"
        if interval == "week":
            y, w, _ = d.isocalendar()
            return f"{y}-W{w:02d}"
        return d.isoformat()

    async def _render_timeline(self, actor, dataset, config, filters):
        date_field = self._need(config, "date_field")
        interval = config.get("interval") or "month"
        if interval not in INTERVALS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"interval must be one of {list(INTERVALS)}")
        m = config.get("measure") or {}
        field, agg = m.get("field"), (m.get("agg") or "count")
        rows = await self._raw(actor, dataset, [date_field] + ([field] if field else []), filters)
        buckets: dict[str, list] = {}
        for r in rows:
            b = self._bucket(r.get(date_field), interval)
            if b:
                buckets.setdefault(b, []).append(r.get(field) if field else 1)
        points = [{"period": k, "value": len(v) if (not field or agg == "count")
                   else _num(self.rb._aggregate(agg, v))} for k, v in sorted(buckets.items())]
        return {"points": points, "interval": interval,
                "measure_label": "count" if not field or agg == "count" else f"{agg}({field})"}

    async def _render_comparison(self, actor, dataset, config, filters):
        date_field = self._need(config, "date_field")
        window = int(config.get("window_days") or 30)
        m = config.get("measure") or {}
        field, agg = m.get("field"), (m.get("agg") or "count")
        dim = config.get("dimension")
        fields = [date_field] + ([field] if field else []) + ([dim] if dim else [])
        rows = await self._raw(actor, dataset, fields, filters)
        today = date.today()
        cur_start, prev_start = today - timedelta(days=window), today - timedelta(days=2 * window)

        def side(r):
            try:
                d = date.fromisoformat(str(r.get(date_field) or "")[:10])
            except ValueError:
                return None
            if cur_start <= d <= today:
                return "current"
            if prev_start <= d < cur_start:
                return "previous"
            return None

        def total(vals):
            return float(len(vals)) if (not field or agg == "count") else _num(self.rb._aggregate(agg, vals))

        halves: dict[str, list] = {"current": [], "previous": []}
        by_dim: dict[str, dict[str, list]] = {}
        for r in rows:
            s = side(r)
            if not s:
                continue
            v = r.get(field) if field else 1
            halves[s].append(v)
            if dim:
                by_dim.setdefault(str(r.get(dim)), {"current": [], "previous": []})[s].append(v)
        cur, prev = total(halves["current"]), total(halves["previous"])
        delta = round(cur - prev, 2)
        delta_pct = round(delta * 100 / prev, 1) if prev else (100.0 if cur else 0.0)
        rows_out = [{"label": k, "current": total(v["current"]), "previous": total(v["previous"])}
                    for k, v in by_dim.items()]
        rows_out.sort(key=lambda r: -r["current"])
        return {"current": cur, "previous": prev, "delta": delta, "delta_pct": delta_pct,
                "window_days": window, "by_dimension": rows_out[:15],
                "measure_label": "count" if not field or agg == "count" else f"{agg}({field})"}

    async def _render_geo(self, actor, dataset, config, filters):
        geo_field = self._need(config, "field")
        points, label = await self._grouped(actor, dataset, geo_field, {"measure": config.get("measure")}, filters)
        if geo_field == "pin_code":
            zones: dict[str, float] = {}
            for p in points:
                digit = str(p["label"] or "")[:1]
                zone = PIN_ZONES.get(digit, "Unknown")
                zones[zone] = zones.get(zone, 0) + p["value"]
            points = [{"label": z, "value": v} for z, v in zones.items()]
        points.sort(key=lambda p: -p["value"])
        total = round(sum(p["value"] for p in points), 2) or 1
        return {"regions": [{"region": p["label"], "value": p["value"],
                             "pct": round(p["value"] * 100 / total, 1)} for p in points[:30]],
                "field": geo_field, "measure_label": label}

    # ---------- drill-down ----------
    async def drilldown(self, actor: User, data: dict) -> dict:
        """Underlying rows behind a datum: dataset base columns filtered by the
        spec's filters AND field == value."""
        dataset = data.get("dataset")
        field = data.get("field")
        if not dataset or not field:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dataset and field are required.")
        cond = (_and(_cond(field, "is_empty", None)) if data.get("value") in (None, "—", "None")
                else _and(_cond(field, "eq", data.get("value"))))
        filters = _merge_filters(data.get("filters"), cond)
        ds = self.rb._dataset(dataset)
        cols = [{"field": c["field"]} for c in ds["columns"]][:8]
        res = await self.rb.run_definition(actor, {"dataset": dataset, "columns": cols, "filters": filters},
                                           limit=int(data.get("limit") or 50))
        return {"columns": res["columns"], "rows": res["rows"], "total": res["total"],
                "field": field, "value": data.get("value")}

    # ---------- saved visualizations ----------
    def _validate_saved(self, data: dict):
        if data.get("viz_type") and data["viz_type"] not in VIZ_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"viz_type must be one of {list(VIZ_TYPES)}")
        if data.get("dataset"):
            self.rb._dataset(data["dataset"])
        if data.get("visibility") and data["visibility"] not in VISIBILITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility.")

    async def _get(self, actor: User, viz_id: uuid.UUID) -> Visualization:
        v = (await self.db.execute(select(Visualization).filter(
            Visualization.id == viz_id, Visualization.organization_id == actor.organization_id,
            Visualization.is_deleted == False))).scalars().first()
        if not v or (v.visibility == "private" and v.created_by != actor.id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visualization not found")
        return v

    async def list_saved(self, actor: User, viz_type: str | None = None) -> list[dict]:
        self.rb._require_manager(actor)
        q = select(Visualization).filter(Visualization.organization_id == actor.organization_id,
                                         Visualization.is_deleted == False)
        if viz_type:
            q = q.filter(Visualization.viz_type == viz_type)
        rows = (await self.db.execute(q.order_by(Visualization.created_at.desc()))).scalars().all()
        return [self._serialize(v) for v in rows
                if v.visibility == "organization" or v.created_by == actor.id]

    async def create(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate_saved(data)
        if not data.get("viz_type") or not data.get("dataset"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="viz_type and dataset are required.")
        v = Visualization(organization_id=actor.organization_id, name=data["name"],
                          description=data.get("description"), viz_type=data["viz_type"],
                          dataset=data["dataset"], config=data.get("config") or {},
                          filters=data.get("filters"), visibility=data.get("visibility") or "organization",
                          is_pinned=bool(data.get("is_pinned", False)), created_by=actor.id)
        self.db.add(v)
        await self.db.flush()
        await self.db.refresh(v)
        return self._serialize(v)

    async def update(self, actor: User, viz_id: uuid.UUID, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate_saved(data)
        v = await self._get(actor, viz_id)
        for f in ("name", "description", "viz_type", "dataset", "config", "filters", "visibility", "is_pinned"):
            if f in data and data[f] is not None:
                setattr(v, f, data[f])
        self.db.add(v)
        await self.db.flush()
        return self._serialize(v)

    async def delete(self, actor: User, viz_id: uuid.UUID) -> None:
        self.rb._require_manager(actor)
        v = await self._get(actor, viz_id)
        v.is_deleted = True
        self.db.add(v)
        await self.db.flush()

    async def render_saved(self, actor: User, viz_id: uuid.UUID) -> dict:
        v = await self._get(actor, viz_id)
        out = await self.render(actor, {"viz_type": v.viz_type, "dataset": v.dataset,
                                        "config": v.config or {}, "filters": v.filters})
        return {**self._serialize(v), **out}

    # ---------- dashboard integration ----------
    async def dashboard(self, actor: User) -> dict:
        """Pinned visualizations rendered for the Home dashboard (best-effort:
        one broken viz never blanks the widget)."""
        self.rb._require_manager(actor)
        rows = (await self.db.execute(select(Visualization).filter(
            Visualization.organization_id == actor.organization_id, Visualization.is_deleted == False,
            Visualization.is_pinned == True).order_by(Visualization.created_at.desc()).limit(8))).scalars().all()
        cards = []
        for v in rows:
            if v.visibility == "private" and v.created_by != actor.id:
                continue
            try:
                out = await self.render(actor, {"viz_type": v.viz_type, "dataset": v.dataset,
                                                "config": v.config or {}, "filters": v.filters})
                cards.append({**self._serialize(v), "data": out["data"]})
            except Exception:
                cards.append({**self._serialize(v), "data": None})
        return {"pinned": cards, "count": len(cards)}

    # ---------- export ----------
    async def export_csv(self, actor: User, viz_id: uuid.UUID) -> str:
        v = await self._get(actor, viz_id)
        out = await self.render(actor, {"viz_type": v.viz_type, "dataset": v.dataset,
                                        "config": v.config or {}, "filters": v.filters})
        return self._to_csv(v.viz_type, out["data"])

    @staticmethod
    def _to_csv(viz_type: str, data: dict) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        if viz_type in ("bar", "line", "area", "pie"):
            w.writerow(["label", "value"])
            [w.writerow([p["label"], p["value"]]) for p in data["points"]]
        elif viz_type == "treemap":
            w.writerow(["name", "value"])
            [w.writerow([n["name"], n["value"]]) for n in data["nodes"]]
        elif viz_type == "funnel":
            w.writerow(["stage", "value", "pct_of_first", "drop_pct"])
            [w.writerow([s["label"], s["value"], s["pct_of_first"], s["drop_pct"]]) for s in data["stages"]]
        elif viz_type == "gauge":
            w.writerow(["value", "target", "pct"])
            w.writerow([data["value"], data["target"], data["pct"]])
        elif viz_type == "timeline":
            w.writerow(["period", "value"])
            [w.writerow([p["period"], p["value"]]) for p in data["points"]]
        elif viz_type == "comparison":
            w.writerow(["label", "current", "previous"])
            w.writerow(["TOTAL", data["current"], data["previous"]])
            [w.writerow([r["label"], r["current"], r["previous"]]) for r in data["by_dimension"]]
        elif viz_type == "geo":
            w.writerow(["region", "value", "pct"])
            [w.writerow([r["region"], r["value"], r["pct"]]) for r in data["regions"]]
        elif viz_type == "heatmap":
            w.writerow([""] + data["cols"])
            for i, rname in enumerate(data["rows"]):
                w.writerow([rname] + data["cells"][i])
        elif viz_type == "pivot":
            w.writerow([data["row_field"]] + data["columns"])
            [w.writerow([r["__row"]] + [r.get(c) for c in data["columns"]]) for r in data["rows"]]
        else:  # table
            keys = [c["key"] for c in data["columns"]]
            w.writerow(keys)
            [w.writerow([r.get(k) for k in keys]) for r in data["rows"]]
        return buf.getvalue()

    # ---------- serialize ----------
    def _serialize(self, v: Visualization) -> dict:
        return {"id": str(v.id), "name": v.name, "description": v.description, "viz_type": v.viz_type,
                "dataset": v.dataset, "config": v.config or {}, "filters": v.filters,
                "visibility": v.visibility, "is_pinned": v.is_pinned,
                "created_at": v.created_at.isoformat() if v.created_at else None}

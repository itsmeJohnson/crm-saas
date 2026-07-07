"""Custom Report Builder — a metadata-driven, safe query engine over existing
datasets. No raw SQL: a report can only read the whitelisted columns and
relations declared in DATASET_CATALOG, always org-scoped (and downline-scoped for
managers). Filtering reuses the Rule Engine evaluator; grouping, sorting,
calculated fields, joins and pivots are applied in Python over a bounded row set.
"""
from __future__ import annotations
import ast
import csv
import io
import importlib
import operator
import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.report_builder import ReportDefinition, ReportVersion
from app.services.audit_service import AuditService
from app.services import rule_evaluator as ev

MAX_ROWS = 20000          # safety cap on scanned rows
AGGREGATIONS = ("count", "sum", "avg", "min", "max")
CHART_TYPES = ("bar", "line", "pie", "table")
FREQUENCIES = ("daily", "weekly", "monthly")
VISIBILITIES = ("private", "organization")


def _rel(model, fk, cols):
    return {"model": model, "fk": fk, "columns": cols}


# dataset key → {model, owner_field (manager scope), columns, relations}
DATASET_CATALOG: dict[str, dict] = {
    "leads": {
        "model": "app.models.lead.Lead", "label": "Leads", "owner_field": "assigned_user_id",
        "columns": [
            {"field": "status", "type": "string"}, {"field": "source", "type": "string"},
            {"field": "priority", "type": "string"}, {"field": "value", "type": "number"},
            {"field": "score", "type": "number"}, {"field": "city", "type": "string"},
            {"field": "company_name", "type": "string"}, {"field": "email", "type": "string"},
            {"field": "created_at", "type": "date"}, {"field": "converted_at", "type": "date"},
        ],
        "relations": {
            "owner": _rel("app.models.user.User", "assigned_user_id",
                          [{"field": "first_name", "type": "string"}, {"field": "last_name", "type": "string"},
                           {"field": "email", "type": "string"}, {"field": "role", "type": "string"}]),
            "company": _rel("app.models.company.Company", "company_id",
                            [{"field": "name", "type": "string"}, {"field": "industry", "type": "string"}]),
            "stage": _rel("app.models.pipeline.PipelineStage", "stage_id",
                          [{"field": "name", "type": "string"}]),
        },
    },
    "contacts": {
        "model": "app.models.contact.Contact", "label": "Contacts", "owner_field": "assigned_user_id",
        "columns": [
            {"field": "first_name", "type": "string"}, {"field": "last_name", "type": "string"},
            {"field": "email", "type": "string"}, {"field": "phone", "type": "string"},
            {"field": "job_title", "type": "string"}, {"field": "created_at", "type": "date"},
        ],
        "relations": {
            "owner": _rel("app.models.user.User", "assigned_user_id",
                          [{"field": "first_name", "type": "string"}, {"field": "role", "type": "string"}]),
            "company": _rel("app.models.company.Company", "company_id",
                            [{"field": "name", "type": "string"}, {"field": "industry", "type": "string"}]),
        },
    },
    "companies": {
        "model": "app.models.company.Company", "label": "Companies", "owner_field": "assigned_user_id",
        "columns": [
            {"field": "name", "type": "string"}, {"field": "industry", "type": "string"},
            {"field": "company_type", "type": "string"}, {"field": "source", "type": "string"},
            {"field": "employee_count", "type": "number"}, {"field": "annual_revenue", "type": "number"},
            {"field": "created_at", "type": "date"},
        ],
        "relations": {
            "owner": _rel("app.models.user.User", "assigned_user_id",
                          [{"field": "first_name", "type": "string"}, {"field": "role", "type": "string"}]),
        },
    },
    "tasks": {
        "model": "app.models.task.Task", "label": "Tasks", "owner_field": "assigned_user_id",
        "columns": [
            {"field": "title", "type": "string"}, {"field": "status", "type": "string"},
            {"field": "priority", "type": "string"}, {"field": "due_date", "type": "date"},
            {"field": "completed_at", "type": "date"}, {"field": "created_at", "type": "date"},
        ],
        "relations": {
            "owner": _rel("app.models.user.User", "assigned_user_id",
                          [{"field": "first_name", "type": "string"}, {"field": "role", "type": "string"}]),
        },
    },
    "activities": {
        "model": "app.models.activity.Activity", "label": "Activities", "owner_field": "assigned_user_id",
        "columns": [
            {"field": "activity_type", "type": "string"}, {"field": "subject", "type": "string"},
            {"field": "status", "type": "string"}, {"field": "call_direction", "type": "string"},
            {"field": "call_duration", "type": "number"}, {"field": "call_disposition", "type": "string"},
            {"field": "created_at", "type": "date"},
        ],
        "relations": {
            "owner": _rel("app.models.user.User", "assigned_user_id",
                          [{"field": "first_name", "type": "string"}, {"field": "role", "type": "string"}]),
        },
    },
    "invoices": {
        "model": "app.models.customer_invoice.CustomerInvoice", "label": "Invoices", "owner_field": None,
        "columns": [
            {"field": "invoice_number", "type": "string"}, {"field": "status", "type": "string"},
            {"field": "currency", "type": "string"}, {"field": "total_amount", "type": "number"},
            {"field": "amount_paid", "type": "number"}, {"field": "issue_date", "type": "date"},
            {"field": "due_date", "type": "date"}, {"field": "created_at", "type": "date"},
        ],
        "relations": {
            "company": _rel("app.models.company.Company", "company_id",
                            [{"field": "name", "type": "string"}, {"field": "industry", "type": "string"}]),
        },
    },
}

# built-in report templates (seeded on demand)
_TEMPLATES = [
    {"name": "Leads by status", "dataset": "leads", "columns": [{"field": "status"}, {"field": "value", "agg": "sum"}],
     "group_by": ["status"], "sort": [{"field": "status", "dir": "asc"}], "chart": {"type": "bar", "x": "status", "y": "value"}},
    {"name": "Pipeline value by owner", "dataset": "leads",
     "columns": [{"field": "owner.first_name"}, {"field": "value", "agg": "sum"}],
     "group_by": ["owner.first_name"], "chart": {"type": "bar", "x": "owner.first_name", "y": "value"}},
    {"name": "Overdue invoices", "dataset": "invoices",
     "columns": [{"field": "invoice_number"}, {"field": "company.name"}, {"field": "total_amount"}, {"field": "amount_paid"}],
     "filters": {"type": "group", "logic": "and", "children": [
         {"type": "condition", "field": "status", "op": "eq", "value": "Overdue"}]},
     "calculated_fields": [{"name": "balance", "expression": "total_amount - amount_paid", "type": "number"}]},
]

_SAFE_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: lambda a, b: a / b if b else 0.0, ast.USub: operator.neg, ast.Mod: lambda a, b: a % b if b else 0.0}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class ReportBuilderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="The report builder is available to managers and admins only.")

    def _can_admin(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    # ---------- catalog ----------
    def catalog(self) -> dict:
        datasets = []
        for key, meta in DATASET_CATALOG.items():
            cols = [{"field": c["field"], "type": c["type"], "label": c["field"]} for c in meta["columns"]]
            for rel, rmeta in meta.get("relations", {}).items():
                for c in rmeta["columns"]:
                    cols.append({"field": f"{rel}.{c['field']}", "type": c["type"], "label": f"{rel}.{c['field']}"})
            datasets.append({"key": key, "label": meta["label"], "columns": cols})
        return {"datasets": datasets, "aggregations": list(AGGREGATIONS),
                "operators": {"comparison": list(ev.COMPARISON_OPS), "date": list(ev.DATE_OPS),
                              "time": list(ev.TIME_OPS), "boolean": list(ev.BOOL_OPS)},
                "logic": list(ev.LOGIC_OPS), "chart_types": list(CHART_TYPES),
                "frequencies": list(FREQUENCIES), "visibilities": list(VISIBILITIES)}

    def _dataset(self, key: str) -> dict:
        d = DATASET_CATALOG.get(key)
        if not d:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown dataset. Allowed: {list(DATASET_CATALOG)}")
        return d

    def _all_fields(self, ds: dict) -> set:
        fields = {c["field"] for c in ds["columns"]}
        for rel, rmeta in ds.get("relations", {}).items():
            fields |= {f"{rel}.{c['field']}" for c in rmeta["columns"]}
        return fields

    # ---------- validation ----------
    def _validate(self, data: dict):
        ds = self._dataset(data.get("dataset"))
        fields = self._all_fields(ds)
        calc_names = {c.get("name") for c in (data.get("calculated_fields") or []) if c.get("name")}
        known = fields | calc_names
        for c in (data.get("columns") or []):
            if c.get("field") not in known:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown column '{c.get('field')}'.")
            if c.get("agg") and c["agg"] not in AGGREGATIONS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid aggregation '{c.get('agg')}'.")
        for g in (data.get("group_by") or []):
            if g not in known:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown group field '{g}'.")
        for s in (data.get("sort") or []):
            if s.get("field") not in known:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown sort field '{s.get('field')}'.")
        for cf in (data.get("calculated_fields") or []):
            if not cf.get("name") or not cf.get("expression"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A calculated field needs a name and expression.")
            self._compile_expr(cf["expression"])  # raises on unsafe/invalid
        pv = data.get("pivot")
        if pv:
            for k in ("row", "col", "measure"):
                if pv.get(k) and pv[k] not in known:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown pivot field '{pv.get(k)}'.")
            if pv.get("agg") and pv["agg"] not in AGGREGATIONS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid pivot aggregation.")
        ch = data.get("chart")
        if ch and ch.get("type") and ch["type"] not in CHART_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid chart type.")
        if data.get("visibility") and data["visibility"] not in VISIBILITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visibility.")

    # ---------- calculated-field safe expression ----------
    def _compile_expr(self, expr: str):
        try:
            tree = ast.parse(expr, mode="eval").body
        except SyntaxError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid expression: {expr}")
        self._check_node(tree)
        return tree

    def _check_node(self, node):
        if isinstance(node, ast.BinOp):
            if type(node.op) not in _SAFE_OPS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported operator in expression.")
            self._check_node(node.left); self._check_node(node.right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _SAFE_OPS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported unary operator.")
            self._check_node(node.operand)
        elif isinstance(node, (ast.Name, ast.Constant, ast.Num)):
            return
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only arithmetic over columns is allowed in calculated fields.")

    def _eval_expr(self, tree, record: dict):
        def ev_(n):
            if isinstance(n, ast.BinOp):
                return _SAFE_OPS[type(n.op)](ev_(n.left), ev_(n.right))
            if isinstance(n, ast.UnaryOp):
                return _SAFE_OPS[type(n.op)](ev_(n.operand))
            if isinstance(n, ast.Constant):
                return _num(n.value)
            if isinstance(n, ast.Num):  # py<3.8 compat
                return _num(n.n)
            if isinstance(n, ast.Name):
                return _num(record.get(n.id))
            return 0.0
        try:
            return round(ev_(tree), 4)
        except Exception:
            return None

    # ================= the engine =================
    async def _scope_owner_ids(self, actor: User) -> set | None:
        if self._can_admin(actor):
            return None
        from app.services.user_service import UserService
        try:
            ids = await UserService(self.db).get_downline_user_ids(actor)
        except Exception:
            ids = set()
        return set(ids) | {actor.id}

    async def run_definition(self, actor: User, d: dict, *, limit: int = 100, offset: int = 0) -> dict:
        self._require_manager(actor)
        self._validate(d)
        ds = self._dataset(d["dataset"])
        Model = self._model(ds["model"])
        # base rows: org-scoped, non-deleted, manager downline-scoped on the owner field
        q = select(Model).filter(Model.organization_id == actor.organization_id, Model.is_deleted == False)
        owner_field = ds.get("owner_field")
        if owner_field:
            scope = await self._scope_owner_ids(actor)
            if scope is not None:
                q = q.filter(getattr(Model, owner_field).in_(list(scope)))
        rows = list((await self.db.execute(q.limit(MAX_ROWS))).scalars().all())
        records = await self._build_records(ds, rows)

        # calculated fields (per row, before grouping)
        calcs = d.get("calculated_fields") or []
        compiled = [(c["name"], self._compile_expr(c["expression"])) for c in calcs]
        for rec in records:
            for name, tree in compiled:
                rec[name] = self._eval_expr(tree, rec)

        # filter via the Rule Engine evaluator
        filters = d.get("filters")
        ctx = {"now": _now(), "current_user_id": actor.id}
        if filters:
            records = [r for r in records if ev.evaluate(filters, r, ctx)]

        pivot = self._pivot(records, d["pivot"]) if d.get("pivot") else None

        columns = d.get("columns") or []
        group_by = d.get("group_by") or []
        if group_by:
            out_cols, result = self._grouped(records, columns, group_by)
        else:
            out_cols = [{"key": c["field"], "label": c.get("label") or c["field"], "agg": None} for c in columns]
            keys = [c["field"] for c in columns]
            result = [{k: rec.get(k) for k in keys} for rec in records]

        result = self._sort(result, d.get("sort") or [], out_cols)
        total = len(result)
        page = result[offset:offset + limit]
        return {"columns": out_cols, "rows": page, "total": total, "scanned": len(records),
                "pivot": pivot, "chart": d.get("chart")}

    async def _build_records(self, ds: dict, rows: list) -> list[dict]:
        base_fields = [c["field"] for c in ds["columns"]]
        records = []
        for r in rows:
            rec = {}
            for f in base_fields:
                v = getattr(r, f, None)
                if isinstance(v, uuid.UUID):
                    v = str(v)
                elif isinstance(v, datetime):
                    v = v.isoformat()
                elif isinstance(v, date):
                    v = v.isoformat()
                elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
                    v = float(v)
                rec[f] = v
            rec["__row"] = r
            records.append(rec)
        # relation joins — batch-load each related model once
        for rel, rmeta in ds.get("relations", {}).items():
            RelModel = self._model(rmeta["model"])
            fk = rmeta["fk"]
            ids = {getattr(rec["__row"], fk, None) for rec in records if getattr(rec["__row"], fk, None)}
            id_map = {}
            if ids:
                related = (await self.db.execute(select(RelModel).filter(RelModel.id.in_(list(ids))))).scalars().all()
                id_map = {ro.id: ro for ro in related}
            for rec in records:
                ro = id_map.get(getattr(rec["__row"], fk, None))
                for c in rmeta["columns"]:
                    v = getattr(ro, c["field"], None) if ro else None
                    if isinstance(v, uuid.UUID):
                        v = str(v)
                    rec[f"{rel}.{c['field']}"] = v
        for rec in records:
            rec.pop("__row", None)
        return records

    @staticmethod
    def _aggregate(agg: str, values: list):
        nums = [_num(v) for v in values if v is not None]
        if agg == "count":
            return len(values)
        if not nums:
            return 0
        if agg == "sum":
            return round(sum(nums), 2)
        if agg == "avg":
            return round(sum(nums) / len(nums), 2)
        if agg == "min":
            return min(nums)
        if agg == "max":
            return max(nums)
        return len(values)

    def _grouped(self, records, columns, group_by):
        out_cols = [{"key": g, "label": g, "agg": None} for g in group_by]
        measures = [c for c in columns if c.get("agg")]
        for m in measures:
            out_cols.append({"key": f"{m['agg']}__{m['field']}", "label": f"{m['agg']}({m['field']})", "agg": m["agg"]})
        if not measures:
            out_cols.append({"key": "count", "label": "count", "agg": "count"})
        buckets: dict = {}
        for rec in records:
            key = tuple(rec.get(g) for g in group_by)
            buckets.setdefault(key, []).append(rec)
        result = []
        for key, recs in buckets.items():
            row = {g: key[i] for i, g in enumerate(group_by)}
            if measures:
                for m in measures:
                    row[f"{m['agg']}__{m['field']}"] = self._aggregate(m["agg"], [r.get(m["field"]) for r in recs])
            else:
                row["count"] = len(recs)
            result.append(row)
        return out_cols, result

    def _sort(self, rows, sort_spec, out_cols):
        valid_keys = {c["key"] for c in out_cols}
        for s in reversed(sort_spec or []):
            f = s.get("field")
            key = f if f in valid_keys else next((c["key"] for c in out_cols if c["key"].endswith(f"__{f}") or c["key"] == f), None)
            if not key:
                continue
            reverse = (s.get("dir") or "asc").lower() == "desc"
            rows = sorted(rows, key=lambda r: (r.get(key) is None, self._sort_key(r.get(key))), reverse=reverse)
        return rows

    @staticmethod
    def _sort_key(v):
        if isinstance(v, (int, float)):
            return v
        return str(v).lower() if v is not None else ""

    def _pivot(self, records, pv: dict):
        row_f, col_f, measure, agg = pv.get("row"), pv.get("col"), pv.get("measure"), pv.get("agg") or "count"
        table: dict = {}
        col_values: list = []
        for rec in records:
            rk, ck = rec.get(row_f), rec.get(col_f)
            if ck not in col_values:
                col_values.append(ck)
            table.setdefault(rk, {}).setdefault(ck, []).append(rec.get(measure) if measure else 1)
        rows = []
        for rk, cols in table.items():
            row = {"__row": rk}
            for ck in col_values:
                row[str(ck)] = self._aggregate(agg, cols.get(ck, []))
            rows.append(row)
        return {"row_field": row_f, "col_field": col_f, "measure": measure, "agg": agg,
                "columns": [str(c) for c in col_values], "rows": rows}

    # ================= CRUD =================
    async def _get(self, actor: User, report_id: uuid.UUID, *, for_write=False) -> ReportDefinition:
        r = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.id == report_id, ReportDefinition.organization_id == actor.organization_id,
            ReportDefinition.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        if for_write and r.created_by != actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner or an admin can modify this report.")
        if not for_write and r.visibility == "private" and r.created_by != actor.id and not self._can_admin(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This report is private.")
        return r

    async def list_reports(self, actor: User, *, box="mine", dataset=None) -> list[dict]:
        q = select(ReportDefinition).filter(ReportDefinition.organization_id == actor.organization_id,
                                            ReportDefinition.is_deleted == False, ReportDefinition.is_template == False)
        if box == "mine":
            q = q.filter(ReportDefinition.created_by == actor.id)
        elif box == "shared":
            q = q.filter(ReportDefinition.visibility == "organization", ReportDefinition.created_by != actor.id)
        else:  # all visible to me
            from sqlalchemy import or_
            q = q.filter(or_(ReportDefinition.created_by == actor.id, ReportDefinition.visibility == "organization"))
        if dataset:
            q = q.filter(ReportDefinition.dataset == dataset)
        rows = (await self.db.execute(q.order_by(ReportDefinition.created_at.desc()))).scalars().all()
        return [self._serialize(r) for r in rows]

    async def get(self, actor: User, report_id: uuid.UUID) -> dict:
        return self._serialize(await self._get(actor, report_id))

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        r = ReportDefinition(
            organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
            dataset=data["dataset"], columns=data.get("columns") or [], filters=data.get("filters"),
            group_by=data.get("group_by"), sort=data.get("sort"), calculated_fields=data.get("calculated_fields"),
            pivot=data.get("pivot"), chart=data.get("chart"),
            is_template=bool(data.get("is_template", False)),
            visibility=data.get("visibility") or "private",
            pinned_to_dashboard=bool(data.get("pinned_to_dashboard", False)), created_by=actor.id)
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        await self._snapshot(actor, r, note="created")
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="REPORT_CREATED", resource_type="report", resource_id=str(r.id),
                                   action_metadata={"name": r.name, "dataset": r.dataset})
        return self._serialize(r)

    async def update(self, actor: User, report_id: uuid.UUID, data: dict) -> dict:
        r = await self._get(actor, report_id, for_write=True)
        merged = {**self._serialize(r), **data, "dataset": data.get("dataset", r.dataset)}
        if any(k in data for k in ("columns", "filters", "group_by", "sort", "calculated_fields", "pivot", "chart", "dataset", "visibility")):
            self._validate(merged)
            await self._snapshot(actor, r, note="before update")
        for f in ("name", "description", "dataset", "columns", "filters", "group_by", "sort",
                  "calculated_fields", "pivot", "chart", "visibility", "pinned_to_dashboard"):
            if f in data:
                setattr(r, f, data[f])
        r.version = (r.version or 1) + 1
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        return self._serialize(r)

    async def delete(self, actor: User, report_id: uuid.UUID) -> None:
        r = await self._get(actor, report_id, for_write=True)
        r.is_deleted = True
        self.db.add(r)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="REPORT_DELETED", resource_type="report", resource_id=str(r.id),
                                   action_metadata={"name": r.name})

    async def clone(self, actor: User, report_id: uuid.UUID) -> dict:
        src = await self._get(actor, report_id)
        d = self._serialize(src)
        d.pop("id", None)
        d["name"] = f"{src.name} (copy)"
        d["is_template"] = False
        d["visibility"] = "private"
        d["pinned_to_dashboard"] = False
        return await self.create(actor, d)

    async def run_saved(self, actor: User, report_id: uuid.UUID, *, limit=100, offset=0) -> dict:
        r = await self._get(actor, report_id)
        r.run_count = (r.run_count or 0) + 1
        r.last_run = _now()
        self.db.add(r)
        await self.db.flush()
        return await self.run_definition(actor, self._serialize(r), limit=limit, offset=offset)

    # ================= versioning =================
    async def _snapshot(self, actor: User, r: ReportDefinition, note=None) -> None:
        last = (await self.db.execute(select(func.max(ReportVersion.version_no)).filter(
            ReportVersion.report_id == r.id))).scalar() or 0
        self.db.add(ReportVersion(organization_id=r.organization_id, report_id=r.id, version_no=last + 1,
                                  snapshot=self._snapshot_fields(r), note=note, created_by=actor.id))
        await self.db.flush()

    def _snapshot_fields(self, r: ReportDefinition) -> dict:
        return {"name": r.name, "description": r.description, "dataset": r.dataset, "columns": r.columns,
                "filters": r.filters, "group_by": r.group_by, "sort": r.sort,
                "calculated_fields": r.calculated_fields, "pivot": r.pivot, "chart": r.chart,
                "visibility": r.visibility}

    async def list_versions(self, actor: User, report_id: uuid.UUID) -> list[dict]:
        await self._get(actor, report_id)
        rows = (await self.db.execute(select(ReportVersion).filter(
            ReportVersion.report_id == report_id, ReportVersion.is_deleted == False)
            .order_by(ReportVersion.version_no.desc()))).scalars().all()
        return [{"id": str(v.id), "version_no": v.version_no, "note": v.note, "snapshot": v.snapshot,
                 "created_at": v.created_at.isoformat() if v.created_at else None} for v in rows]

    async def restore_version(self, actor: User, report_id: uuid.UUID, version_no: int) -> dict:
        r = await self._get(actor, report_id, for_write=True)
        v = (await self.db.execute(select(ReportVersion).filter(
            ReportVersion.report_id == report_id, ReportVersion.version_no == version_no,
            ReportVersion.is_deleted == False))).scalars().first()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        await self._snapshot(actor, r, note=f"before restore to v{version_no}")
        for f, val in (v.snapshot or {}).items():
            setattr(r, f, val)
        r.version = (r.version or 1) + 1
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        return self._serialize(r)

    # ================= templates =================
    async def seed_templates(self, actor: User) -> dict:
        self._require_manager(actor)
        created = 0
        for tpl in _TEMPLATES:
            exists = (await self.db.execute(select(ReportDefinition).filter(
                ReportDefinition.organization_id == actor.organization_id, ReportDefinition.name == tpl["name"],
                ReportDefinition.is_template == True, ReportDefinition.is_deleted == False))).scalars().first()
            if exists:
                continue
            self.db.add(ReportDefinition(organization_id=actor.organization_id, name=tpl["name"], dataset=tpl["dataset"],
                                         columns=tpl.get("columns") or [], filters=tpl.get("filters"),
                                         group_by=tpl.get("group_by"), sort=tpl.get("sort"),
                                         calculated_fields=tpl.get("calculated_fields"), chart=tpl.get("chart"),
                                         is_template=True, visibility="organization", created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"created": created}

    async def list_templates(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.organization_id == actor.organization_id, ReportDefinition.is_template == True,
            ReportDefinition.is_deleted == False).order_by(ReportDefinition.name.asc()))).scalars().all()
        return [self._serialize(r) for r in rows]

    async def instantiate_template(self, actor: User, report_id: uuid.UUID) -> dict:
        tpl = await self._get(actor, report_id)
        d = self._serialize(tpl)
        d.pop("id", None)
        d["is_template"] = False
        d["visibility"] = "private"
        return await self.create(actor, d)

    # ================= scheduling =================
    def _compute_next(self, frequency: str, base: datetime | None = None) -> datetime:
        base = base or _now()
        return base + {"daily": timedelta(days=1), "weekly": timedelta(weeks=1),
                       "monthly": timedelta(days=30)}.get(frequency, timedelta(days=1))

    async def set_schedule(self, actor: User, report_id: uuid.UUID, data: dict) -> dict:
        r = await self._get(actor, report_id, for_write=True)
        freq = data.get("schedule_frequency")
        if freq and freq not in FREQUENCIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"frequency must be one of {list(FREQUENCIES)}")
        r.schedule_frequency = freq
        r.schedule_recipients = data.get("schedule_recipients") or []
        r.next_run = self._compute_next(freq) if freq else None
        self.db.add(r)
        await self.db.flush()
        await self.db.refresh(r)
        return self._serialize(r)

    async def run_scheduled(self, org_id: uuid.UUID) -> int:
        """Cron entry: deliver due scheduled reports to recipients as notifications."""
        from app.services.notification_service import NotificationService
        now = _now()
        due = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.organization_id == org_id, ReportDefinition.is_deleted == False,
            ReportDefinition.schedule_frequency.isnot(None), ReportDefinition.next_run.isnot(None),
            ReportDefinition.next_run <= now))).scalars().all()
        notifier = NotificationService(self.db)
        sent = 0
        for r in due:
            owner = (await self.db.execute(select(User).filter(User.id == r.created_by))).scalars().first()
            if owner:
                try:
                    res = await self.run_definition(owner, self._serialize(r), limit=1)
                    total = res.get("total", 0)
                except Exception:
                    total = 0
                for uid in (r.schedule_recipients or []) + [str(r.created_by)]:
                    try:
                        await notifier.create_notification(
                            organization_id=org_id, user_id=uuid.UUID(str(uid)), category="report",
                            title=f"Report: {r.name}", body=f"Your scheduled report '{r.name}' is ready ({total} rows).",
                            link_url="/report-builder", action_metadata={"report_id": str(r.id)})
                    except Exception:
                        pass
            r.last_run = now
            r.run_count = (r.run_count or 0) + 1
            r.next_run = self._compute_next(r.schedule_frequency, now)
            self.db.add(r)
            sent += 1
        await self.db.flush()
        return sent

    # ================= dashboard integration =================
    async def dashboard(self, actor: User) -> dict:
        from sqlalchemy import or_
        rows = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.organization_id == actor.organization_id, ReportDefinition.is_deleted == False,
            ReportDefinition.pinned_to_dashboard == True,
            or_(ReportDefinition.created_by == actor.id, ReportDefinition.visibility == "organization"))
            .order_by(ReportDefinition.created_at.desc()).limit(6))).scalars().all()
        cards = []
        for r in rows:
            try:
                res = await self.run_definition(actor, self._serialize(r), limit=5)
            except Exception:
                res = {"columns": [], "rows": [], "total": 0, "chart": r.chart}
            cards.append({"id": str(r.id), "name": r.name, "dataset": r.dataset, "chart": r.chart,
                          "columns": res["columns"], "rows": res["rows"], "total": res["total"]})
        return {"reports": cards}

    # ================= export =================
    async def export_csv(self, actor: User, report_id: uuid.UUID) -> str:
        r = await self._get(actor, report_id)
        res = await self.run_definition(actor, self._serialize(r), limit=MAX_ROWS)
        buf = io.StringIO()
        w = csv.writer(buf)
        headers = [c["label"] for c in res["columns"]]
        keys = [c["key"] for c in res["columns"]]
        w.writerow(headers)
        for row in res["rows"]:
            w.writerow([row.get(k) for k in keys])
        return buf.getvalue()

    # ---------- helpers ----------
    @staticmethod
    def _model(path: str):
        mod, cls = path.rsplit(".", 1)
        return getattr(importlib.import_module(mod), cls)

    def _serialize(self, r: ReportDefinition) -> dict:
        return {"id": str(r.id), "name": r.name, "description": r.description, "dataset": r.dataset,
                "columns": r.columns or [], "filters": r.filters, "group_by": r.group_by, "sort": r.sort,
                "calculated_fields": r.calculated_fields, "pivot": r.pivot, "chart": r.chart,
                "is_template": r.is_template, "visibility": r.visibility,
                "pinned_to_dashboard": r.pinned_to_dashboard, "schedule_frequency": r.schedule_frequency,
                "schedule_recipients": r.schedule_recipients or [],
                "next_run": r.next_run.isoformat() if r.next_run else None,
                "last_run": r.last_run.isoformat() if r.last_run else None,
                "run_count": r.run_count, "version": r.version, "created_by": str(r.created_by),
                "created_at": r.created_at.isoformat() if r.created_at else None}

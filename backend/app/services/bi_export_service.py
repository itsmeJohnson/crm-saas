"""Export & BI Integration.

One export layer over the Report Builder's safe query engine:

* On-demand exports of any dataset or saved report as CSV / Excel / PDF / JSON
  (downloads via the REST API), every export recorded in export_jobs and the
  audit log.
* BI feeds — per-org API tokens (bi_tokens) that let Power BI, Tableau, Looker
  and Metabase pull JSON/CSV over plain token-authenticated URLs (no JWT), with
  per-tool connection instructions and an optional created_since incremental
  cursor.
* Webhook Export — push a snapshot to any URL (httpx, retried).
* Cloud Storage — pluggable per-org destination: local directory (default) or
  S3 via boto3 when configured (bi_settings).
* Data Sync — recurring full/incremental pushes (bi_sync_configs) delivered to
  webhook or cloud storage from the daily cron.

Reuses ReportBuilderService for data + permissions, ScheduledReportService's
format builders, AuditService for audit logs. Existing per-module CSV exports
are untouched.
"""
from __future__ import annotations
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.report_builder import ReportDefinition
from app.models.bi_export import BIToken, BISetting, ExportJob, BISyncConfig
from app.services.report_builder_service import ReportBuilderService, DATASET_CATALOG
from app.services.scheduled_report_service import ScheduledReportService, _advance
from app.services.audit_service import AuditService

FORMATS = ("csv", "xlsx", "pdf", "json")
SYNC_FORMATS = ("csv", "xlsx", "json")
DESTINATIONS = ("webhook", "cloud")
SYNC_MODES = ("full", "incremental")
SYNC_FREQUENCIES = ("daily", "weekly", "monthly")
STORAGE_PROVIDERS = ("local", "s3")
LOCAL_EXPORT_DIR = "uploads/exports"

MIMES = {"csv": "text/csv", "json": "application/json", "pdf": "application/pdf",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

CONNECTORS = [
    {"tool": "powerbi", "label": "Power BI",
     "steps": ["Get Data → Web", "Paste the JSON feed URL for your dataset",
               "Power Query auto-detects the rows — expand the `rows` list into columns",
               "Schedule refresh in the Power BI service; the token in the URL authenticates each pull"],
     "url_template": "{base}/api/v1/bi/feed/{token}/dataset/{dataset}.json"},
    {"tool": "tableau", "label": "Tableau",
     "steps": ["Connect → To a Server → Web Data Connector (or use the CSV URL with 'Text file' after downloading)",
               "Tableau reads the CSV feed URL directly via Data → New Data Source",
               "Refresh extracts on your schedule — the token authenticates each pull"],
     "url_template": "{base}/api/v1/bi/feed/{token}/dataset/{dataset}.csv"},
    {"tool": "looker", "label": "Looker Studio",
     "steps": ["Create → Data source → looker studio JSON/CSV connector (community connectors accept a URL)",
               "Paste the JSON feed URL; fields are typed automatically",
               "Use `?created_since=` for incremental refreshes"],
     "url_template": "{base}/api/v1/bi/feed/{token}/dataset/{dataset}.json"},
    {"tool": "metabase", "label": "Metabase",
     "steps": ["Metabase reads SQL databases natively — for API pulls use the CSV/JSON feed URL from a scheduled script",
               "Or add the feed as a Metabase 'Saved question' source via the API",
               "For live dashboards, point a sync (Data Sync tab) at your warehouse ingestion webhook"],
     "url_template": "{base}/api/v1/bi/feed/{token}/dataset/{dataset}.csv"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BIExportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rb = ReportBuilderService(db)
        self.audit = AuditService(db)

    # ---------- meta ----------
    def meta(self) -> dict:
        return {"formats": list(FORMATS), "sync_formats": list(SYNC_FORMATS),
                "destinations": list(DESTINATIONS), "modes": list(SYNC_MODES),
                "frequencies": list(SYNC_FREQUENCIES), "storage_providers": list(STORAGE_PROVIDERS),
                "datasets": [{"key": k, "label": v["label"]} for k, v in DATASET_CATALOG.items()],
                "connectors": CONNECTORS}

    # ---------- data fetch (reuses the report builder engine) ----------
    async def _fetch(self, actor: User, source_type: str, source_key: str,
                     created_since: str | None = None) -> tuple[dict, str]:
        """Returns (run result, export name). Runs as `actor` — org + downline
        scoping and the manager gate come from the report builder."""
        if source_type == "report":
            r = (await self.db.execute(select(ReportDefinition).filter(
                ReportDefinition.id == uuid.UUID(str(source_key)),
                ReportDefinition.organization_id == actor.organization_id,
                ReportDefinition.is_deleted == False))).scalars().first()
            if not r:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
            res = await self.rb.run_definition(actor, self.rb._serialize(r), limit=20000)
            name = r.name
        else:
            ds = self.rb._dataset(source_key)
            cols = [{"field": c["field"]} for c in ds["columns"]]
            res = await self.rb.run_definition(actor, {"dataset": source_key, "columns": cols}, limit=20000)
            name = ds["label"]
        if created_since:
            try:
                cutoff = str(created_since)[:19]
                res = {**res, "rows": [r for r in res["rows"]
                                       if str(r.get("created_at") or "")[:19] >= cutoff]}
                res["total"] = len(res["rows"])
            except Exception:
                pass
        return res, name

    def _bytes(self, fmt: str, res: dict, name: str) -> bytes:
        if fmt == "csv":
            return ScheduledReportService._csv_bytes(res)
        if fmt == "xlsx":
            return ScheduledReportService._xlsx_bytes(res, name)
        if fmt == "pdf":
            return ScheduledReportService._pdf_bytes(res, name)
        return json.dumps({"name": name, "generated_at": _now().isoformat(), "total": res.get("total", 0),
                           "columns": [c["key"] for c in res["columns"]], "rows": res["rows"]},
                          default=str).encode("utf-8")

    async def _log_job(self, org_id, *, kind, source_type, source_key, fmt, target=None,
                       ok=True, rows=0, size=0, error=None, detail=None, actor_id=None) -> ExportJob:
        job = ExportJob(organization_id=org_id, kind=kind, source_type=source_type,
                        source_key=str(source_key)[:64], format=fmt, target=target,
                        status="success" if ok else "failed", rows=rows, size_bytes=size,
                        error=error, detail=detail, created_by=actor_id)
        self.db.add(job)
        await self.db.flush()
        try:
            await self.audit.log_event(
                organization_id=org_id, actor_user_id=actor_id, action="DATA_EXPORTED",
                resource_type="bi_export", resource_id=str(job.id),
                action_metadata={"kind": kind, "source": f"{source_type}:{source_key}", "format": fmt,
                                 "rows": rows, "status": job.status, "target": target})
        except Exception:
            pass
        return job

    # ---------- on-demand download (CSV/Excel/PDF/JSON over the REST API) ----------
    async def export_download(self, actor: User, source_type: str, source_key: str, fmt: str) -> tuple[bytes, str, str]:
        if fmt not in FORMATS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"format must be one of {list(FORMATS)}")
        res, name = await self._fetch(actor, source_type, source_key)
        content = self._bytes(fmt, res, name)
        await self._log_job(actor.organization_id, kind="download", source_type=source_type,
                            source_key=source_key, fmt=fmt, rows=res.get("total", 0),
                            size=len(content), actor_id=actor.id)
        return content, MIMES[fmt], f"{name}.{fmt}".replace("/", "-")

    # ---------- webhook export ----------
    async def webhook_export(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        fmt = data.get("format") or "json"
        if fmt not in ("json", "csv"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook exports support json or csv.")
        res, name = await self._fetch(actor, data.get("source_type") or "dataset", data["source_key"])
        ok, error = await self._post_webhook(data["url"], fmt, res, name)
        job = await self._log_job(actor.organization_id, kind="webhook", source_type=data.get("source_type") or "dataset",
                                  source_key=data["source_key"], fmt=fmt, target=data["url"], ok=ok,
                                  rows=res.get("total", 0), error=error, actor_id=actor.id)
        return {"status": job.status, "rows": job.rows, "error": error, "job_id": str(job.id)}

    async def _post_webhook(self, url: str, fmt: str, res: dict, name: str) -> tuple[bool, str | None]:
        import httpx
        if fmt == "csv":
            body = self._bytes("csv", res, name)
            headers = {"Content-Type": "text/csv", "X-Export-Name": name}
            payload = None
        else:
            payload = {"name": name, "generated_at": _now().isoformat(), "total": res.get("total", 0),
                       "columns": [c["key"] for c in res["columns"]], "rows": res["rows"]}
            body, headers = None, None
        last_err = None
        for _ in range(3):  # initial attempt + 2 retries
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    if payload is not None:
                        r = await client.post(url, json=payload)
                    else:
                        r = await client.post(url, content=body, headers=headers)
                if r.status_code < 300:
                    return True, None
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)[:200]
        return False, last_err

    # ---------- cloud storage ----------
    async def get_settings(self, actor: User) -> dict:
        self.rb._require_manager(actor)
        s = await self._settings_row(actor.organization_id)
        return self._serialize_settings(s)

    async def _settings_row(self, org_id: uuid.UUID) -> BISetting:
        s = (await self.db.execute(select(BISetting).filter(
            BISetting.organization_id == org_id, BISetting.is_deleted == False))).scalars().first()
        if not s:
            s = BISetting(organization_id=org_id)
            self.db.add(s)
            await self.db.flush()
        return s

    async def update_settings(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        if data.get("storage_provider") and data["storage_provider"] not in STORAGE_PROVIDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"storage_provider must be one of {list(STORAGE_PROVIDERS)}")
        s = await self._settings_row(actor.organization_id)
        for f in ("storage_provider", "s3_bucket", "s3_region", "s3_access_key", "s3_secret_key", "s3_prefix"):
            if f in data and data[f] is not None:
                setattr(s, f, data[f])
        self.db.add(s)
        await self.db.flush()
        return self._serialize_settings(s)

    def _store(self, s: BISetting, org_id: uuid.UUID, filename: str, content: bytes,
               path_prefix: str | None = None) -> str:
        """Write an export artifact to the org's storage destination; returns the path/key."""
        safe = filename.replace("/", "-")
        prefix = (path_prefix or "").strip("/")
        if s.storage_provider == "s3":
            if not s.s3_bucket:
                raise RuntimeError("S3 storage is not configured (bucket missing).")
            import boto3
            key = "/".join(x for x in [(s.s3_prefix or "").strip("/"), prefix, safe] if x)
            client = boto3.client("s3", region_name=s.s3_region,
                                  aws_access_key_id=s.s3_access_key, aws_secret_access_key=s.s3_secret_key)
            client.put_object(Bucket=s.s3_bucket, Key=key, Body=content)
            return f"s3://{s.s3_bucket}/{key}"
        base = os.path.join(LOCAL_EXPORT_DIR, str(org_id), prefix) if prefix else os.path.join(LOCAL_EXPORT_DIR, str(org_id))
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, safe)
        with open(path, "wb") as f:
            f.write(content)
        return path

    async def cloud_export(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        fmt = data.get("format") or "csv"
        if fmt not in FORMATS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"format must be one of {list(FORMATS)}")
        res, name = await self._fetch(actor, data.get("source_type") or "dataset", data["source_key"])
        content = self._bytes(fmt, res, name)
        s = await self._settings_row(actor.organization_id)
        ok, target, error = True, None, None
        try:
            stamp = _now().strftime("%Y%m%d-%H%M%S")
            target = self._store(s, actor.organization_id, f"{name}-{stamp}.{fmt}", content,
                                 data.get("path_prefix"))
        except Exception as e:
            ok, error = False, str(e)[:300]
        job = await self._log_job(actor.organization_id, kind="cloud", source_type=data.get("source_type") or "dataset",
                                  source_key=data["source_key"], fmt=fmt, target=target, ok=ok,
                                  rows=res.get("total", 0), size=len(content), error=error, actor_id=actor.id)
        return {"status": job.status, "target": target, "rows": job.rows, "error": error, "job_id": str(job.id)}

    # ---------- BI tokens & public feed ----------
    async def create_token(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        for d in (data.get("datasets") or []):
            self.rb._dataset(d)
        t = BIToken(organization_id=actor.organization_id, name=data["name"],
                    token=secrets.token_urlsafe(32)[:64], datasets=data.get("datasets"),
                    created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        return self._serialize_token(t, reveal=True)

    async def list_tokens(self, actor: User) -> list[dict]:
        self.rb._require_manager(actor)
        rows = (await self.db.execute(select(BIToken).filter(
            BIToken.organization_id == actor.organization_id, BIToken.is_deleted == False)
            .order_by(BIToken.created_at.desc()))).scalars().all()
        return [self._serialize_token(t) for t in rows]

    async def _get_token_row(self, actor: User, token_id: uuid.UUID) -> BIToken:
        t = (await self.db.execute(select(BIToken).filter(
            BIToken.id == token_id, BIToken.organization_id == actor.organization_id,
            BIToken.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        return t

    async def update_token(self, actor: User, token_id: uuid.UUID, data: dict) -> dict:
        self.rb._require_manager(actor)
        t = await self._get_token_row(actor, token_id)
        for d in (data.get("datasets") or []):
            self.rb._dataset(d)
        for f in ("name", "datasets", "is_active"):
            if f in data and data[f] is not None:
                setattr(t, f, data[f])
        self.db.add(t)
        await self.db.flush()
        return self._serialize_token(t)

    async def rotate_token(self, actor: User, token_id: uuid.UUID) -> dict:
        self.rb._require_manager(actor)
        t = await self._get_token_row(actor, token_id)
        t.token = secrets.token_urlsafe(32)[:64]
        self.db.add(t)
        await self.db.flush()
        return self._serialize_token(t, reveal=True)

    async def delete_token(self, actor: User, token_id: uuid.UUID) -> None:
        self.rb._require_manager(actor)
        t = await self._get_token_row(actor, token_id)
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    async def _resolve_token(self, token: str) -> tuple[BIToken, User]:
        t = (await self.db.execute(select(BIToken).filter(
            BIToken.token == token, BIToken.is_active == True, BIToken.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
        owner = (await self.db.execute(select(User).filter(User.id == t.created_by))).scalars().first()
        if not owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
        t.last_used_at = _now()
        t.use_count = (t.use_count or 0) + 1
        self.db.add(t)
        await self.db.flush()
        return t, owner

    async def feed_index(self, token: str) -> dict:
        t, _ = await self._resolve_token(token)
        allowed = t.datasets or list(DATASET_CATALOG.keys())
        return {"organization_id": str(t.organization_id), "token_name": t.name,
                "datasets": [{"key": k, "label": DATASET_CATALOG[k]["label"],
                              "columns": [c["field"] for c in DATASET_CATALOG[k]["columns"]]}
                             for k in allowed if k in DATASET_CATALOG],
                "formats": ["json", "csv"], "incremental_param": "created_since"}

    async def feed_data(self, token: str, source_type: str, source_key: str, fmt: str,
                        created_since: str | None = None) -> tuple[bytes, str, str]:
        if fmt not in ("json", "csv"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Feeds serve json or csv.")
        t, owner = await self._resolve_token(token)
        if source_type == "dataset" and t.datasets and source_key not in t.datasets:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This token cannot read that dataset.")
        res, name = await self._fetch(owner, source_type, source_key, created_since=created_since)
        content = self._bytes(fmt, res, name)
        try:
            await self.audit.log_event(
                organization_id=t.organization_id, actor_user_id=t.created_by, action="BI_FEED_ACCESSED",
                resource_type="bi_token", resource_id=str(t.id),
                action_metadata={"source": f"{source_type}:{source_key}", "format": fmt,
                                 "rows": res.get("total", 0), "created_since": created_since})
        except Exception:
            pass
        return content, MIMES[fmt], f"{name}.{fmt}".replace("/", "-")

    # ---------- data sync ----------
    def _validate_sync(self, data: dict):
        if data.get("format") and data["format"] not in SYNC_FORMATS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"format must be one of {list(SYNC_FORMATS)}")
        if data.get("destination") and data["destination"] not in DESTINATIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"destination must be one of {list(DESTINATIONS)}")
        if data.get("mode") and data["mode"] not in SYNC_MODES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"mode must be one of {list(SYNC_MODES)}")
        if data.get("frequency") and data["frequency"] not in SYNC_FREQUENCIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"frequency must be one of {list(SYNC_FREQUENCIES)}")

    async def create_sync(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate_sync(data)
        if (data.get("destination") or "webhook") == "webhook" and not data.get("target_url"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook syncs need target_url.")
        if data.get("source_type", "dataset") == "dataset":
            self.rb._dataset(data["source_key"])
        c = BISyncConfig(organization_id=actor.organization_id, name=data["name"],
                         source_type=data.get("source_type") or "dataset", source_key=str(data["source_key"]),
                         format=data.get("format") or "json", destination=data.get("destination") or "webhook",
                         target_url=data.get("target_url"), path_prefix=data.get("path_prefix"),
                         mode=data.get("mode") or "full", frequency=data.get("frequency") or "daily",
                         is_active=bool(data.get("is_active", True)),
                         next_run_at=_advance(data.get("frequency") or "daily"), created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        return self._serialize_sync(c)

    async def list_syncs(self, actor: User) -> list[dict]:
        self.rb._require_manager(actor)
        rows = (await self.db.execute(select(BISyncConfig).filter(
            BISyncConfig.organization_id == actor.organization_id, BISyncConfig.is_deleted == False)
            .order_by(BISyncConfig.created_at.desc()))).scalars().all()
        return [self._serialize_sync(c) for c in rows]

    async def _get_sync(self, actor: User, sync_id: uuid.UUID) -> BISyncConfig:
        c = (await self.db.execute(select(BISyncConfig).filter(
            BISyncConfig.id == sync_id, BISyncConfig.organization_id == actor.organization_id,
            BISyncConfig.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync not found")
        return c

    async def update_sync(self, actor: User, sync_id: uuid.UUID, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate_sync(data)
        c = await self._get_sync(actor, sync_id)
        for f in ("name", "format", "destination", "target_url", "path_prefix", "mode", "is_active"):
            if f in data and data[f] is not None:
                setattr(c, f, data[f])
        if data.get("frequency") and data["frequency"] != c.frequency:
            c.frequency = data["frequency"]
            c.next_run_at = _advance(c.frequency)
        self.db.add(c)
        await self.db.flush()
        return self._serialize_sync(c)

    async def delete_sync(self, actor: User, sync_id: uuid.UUID) -> None:
        self.rb._require_manager(actor)
        c = await self._get_sync(actor, sync_id)
        c.is_deleted = True
        self.db.add(c)
        await self.db.flush()

    async def run_sync(self, c: BISyncConfig, *, actor_id: uuid.UUID | None = None) -> ExportJob:
        """Execute one sync run (never raises): fetch (incremental via the
        created_at cursor), deliver, log, advance the cursor on success."""
        owner = (await self.db.execute(select(User).filter(User.id == c.created_by))).scalars().first()
        ok, error, target, rows, size = False, None, None, 0, 0
        started_cursor = c.last_cursor if c.mode == "incremental" else None
        try:
            if not owner:
                raise RuntimeError("Sync owner not found")
            res, name = await self._fetch(owner, c.source_type, c.source_key, created_since=started_cursor)
            rows = res.get("total", 0)
            content = self._bytes(c.format, res, name)
            size = len(content)
            if c.destination == "webhook":
                target = c.target_url
                ok, error = await self._post_webhook(c.target_url, "json" if c.format == "json" else "csv", res, name)
            else:
                s = await self._settings_row(c.organization_id)
                stamp = _now().strftime("%Y%m%d-%H%M%S")
                target = self._store(s, c.organization_id, f"{name}-{stamp}.{c.format}", content, c.path_prefix)
                ok = True
        except Exception as e:
            error = str(e)[:300]
        job = await self._log_job(c.organization_id, kind="sync", source_type=c.source_type,
                                  source_key=c.source_key, fmt=c.format, target=target, ok=ok,
                                  rows=rows, size=size, error=error,
                                  detail={"sync_id": str(c.id), "mode": c.mode, "cursor": started_cursor},
                                  actor_id=actor_id)
        c.last_run_at = _now()
        c.last_status = job.status
        c.run_count = (c.run_count or 0) + 1
        if ok and c.mode == "incremental":
            c.last_cursor = _now().isoformat()[:19]
        self.db.add(c)
        await self.db.flush()
        return job

    async def run_sync_now(self, actor: User, sync_id: uuid.UUID) -> dict:
        self.rb._require_manager(actor)
        c = await self._get_sync(actor, sync_id)
        job = await self.run_sync(c, actor_id=actor.id)
        return {"status": job.status, "rows": job.rows, "target": job.target, "error": job.error}

    async def scan(self, org_id: uuid.UUID) -> dict:
        """Cron: run every due active sync for one org and advance next_run_at."""
        due = (await self.db.execute(select(BISyncConfig).filter(
            BISyncConfig.organization_id == org_id, BISyncConfig.is_deleted == False,
            BISyncConfig.is_active == True, BISyncConfig.next_run_at.isnot(None),
            BISyncConfig.next_run_at <= _now()))).scalars().all()
        synced = failed = 0
        for c in due:
            job = await self.run_sync(c)
            if job.status == "success":
                synced += 1
            else:
                failed += 1
            c.next_run_at = _advance(c.frequency)
            self.db.add(c)
        await self.db.flush()
        return {"due": len(due), "synced": synced, "failed": failed}

    # ---------- history & dashboard ----------
    async def history(self, actor: User, kind: str | None = None, limit: int = 100) -> list[dict]:
        self.rb._require_manager(actor)
        q = select(ExportJob).filter(ExportJob.organization_id == actor.organization_id,
                                     ExportJob.is_deleted == False)
        if kind:
            q = q.filter(ExportJob.kind == kind)
        rows = (await self.db.execute(q.order_by(ExportJob.created_at.desc())
                                      .limit(min(limit, 300)))).scalars().all()
        return [self._serialize_job(j) for j in rows]

    async def dashboard(self, actor: User) -> dict:
        self.rb._require_manager(actor)
        org = actor.organization_id
        tokens = (await self.db.execute(select(func.count(BIToken.id)).filter(
            BIToken.organization_id == org, BIToken.is_deleted == False, BIToken.is_active == True))).scalar() or 0
        syncs = (await self.db.execute(select(func.count(BISyncConfig.id)).filter(
            BISyncConfig.organization_id == org, BISyncConfig.is_deleted == False,
            BISyncConfig.is_active == True))).scalar() or 0
        by_kind: dict = {}
        for kind in ("download", "webhook", "cloud", "sync"):
            by_kind[kind] = (await self.db.execute(select(func.count(ExportJob.id)).filter(
                ExportJob.organization_id == org, ExportJob.is_deleted == False,
                ExportJob.kind == kind))).scalar() or 0
        total = sum(by_kind.values())
        failed = (await self.db.execute(select(func.count(ExportJob.id)).filter(
            ExportJob.organization_id == org, ExportJob.is_deleted == False,
            ExportJob.status == "failed"))).scalar() or 0
        recent = (await self.db.execute(select(ExportJob).filter(
            ExportJob.organization_id == org, ExportJob.is_deleted == False)
            .order_by(ExportJob.created_at.desc()).limit(8))).scalars().all()
        return {"active_tokens": tokens, "active_syncs": syncs, "exports": total, "failed": failed,
                "success_rate": round((total - failed) * 100 / total, 1) if total else 0.0,
                "by_kind": by_kind, "recent": [self._serialize_job(j) for j in recent]}

    # ---------- serializers ----------
    @staticmethod
    def _serialize_token(t: BIToken, reveal: bool = False) -> dict:
        return {"id": str(t.id), "name": t.name,
                "token": t.token if reveal else f"…{t.token[-6:]}",
                "datasets": t.datasets, "is_active": t.is_active,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "use_count": t.use_count,
                "created_at": t.created_at.isoformat() if t.created_at else None}

    @staticmethod
    def _serialize_settings(s: BISetting) -> dict:
        return {"storage_provider": s.storage_provider, "s3_bucket": s.s3_bucket,
                "s3_region": s.s3_region, "s3_prefix": s.s3_prefix,
                "s3_access_key": f"…{s.s3_access_key[-4:]}" if s.s3_access_key else None,
                "s3_secret_key": "••••" if s.s3_secret_key else None}

    @staticmethod
    def _serialize_sync(c: BISyncConfig) -> dict:
        return {"id": str(c.id), "name": c.name, "source_type": c.source_type, "source_key": c.source_key,
                "format": c.format, "destination": c.destination, "target_url": c.target_url,
                "path_prefix": c.path_prefix, "mode": c.mode, "last_cursor": c.last_cursor,
                "frequency": c.frequency, "is_active": c.is_active,
                "next_run_at": c.next_run_at.isoformat() if c.next_run_at else None,
                "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
                "last_status": c.last_status, "run_count": c.run_count,
                "created_at": c.created_at.isoformat() if c.created_at else None}

    @staticmethod
    def _serialize_job(j: ExportJob) -> dict:
        return {"id": str(j.id), "kind": j.kind, "source_type": j.source_type, "source_key": j.source_key,
                "format": j.format, "target": j.target, "status": j.status, "rows": j.rows,
                "size_bytes": j.size_bytes, "error": j.error, "detail": j.detail,
                "created_at": j.created_at.isoformat() if j.created_at else None}

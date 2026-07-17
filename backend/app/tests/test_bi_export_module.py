import json
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.audit_log import AuditLog
from app.models.bi_export import ExportJob, BISyncConfig
from app.services.bi_export_service import BIExportService
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    store = {}
    async def g(k): return store.get(k)
    async def s(k, v, ex=300): store[k] = v; return True
    async def d(k): store.pop(k, None); return True
    monkeypatch.setattr(redis_client, "get", g)
    monkeypatch.setattr(redis_client, "set", s)
    monkeypatch.setattr(redis_client, "delete", d)
    from app.dependencies import feature_guard
    async def feats(*a, **k): return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(client: AsyncClient, db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "BI Org", "slug": "bi-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@bi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@bi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    # backdate created_at so incremental cursors (second precision) always exclude them
    backdated = datetime.now(timezone.utc) - timedelta(hours=1)
    for i, st in enumerate(["New", "New", "Contacted"]):
        db.add(Lead(organization_id=org.id, last_name=f"L{i}", title="t", status=st, value=100 * (i + 1),
                    assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id, created_at=backdated))
    await db.commit()
    h_admin = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    r = await client.post("/api/v1/report-builder", json={
        "name": "BI leads report", "dataset": "leads",
        "columns": [{"field": "status"}, {"field": "value"}]}, headers=h_admin)
    assert r.status_code == 201, r.text
    return {"org": org, "admin": admin, "emp": emp, "report_id": r.json()["id"], "h_admin": h_admin,
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_meta_and_connectors(client: AsyncClient, setup):
    r = await client.get("/api/v1/bi/meta", headers=setup["h_admin"])
    body = r.json()
    assert set(body["formats"]) == {"csv", "xlsx", "pdf", "json"}
    tools = {c["tool"] for c in body["connectors"]}
    assert tools == {"powerbi", "tableau", "looker", "metabase"}
    assert any(d["key"] == "leads" for d in body["datasets"])


@pytest.mark.asyncio
async def test_download_all_formats_logged_and_audited(client: AsyncClient, setup, db: AsyncSession):
    for fmt, mime_part in (("csv", "text/csv"), ("json", "application/json"),
                           ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        r = await client.get("/api/v1/bi/export", headers=setup["h_admin"],
                             params={"source_type": "dataset", "source_key": "leads", "format": fmt})
        assert r.status_code == 200, (fmt, r.text)
        assert mime_part in r.headers["content-type"]
        assert len(r.content) > 0
    payload = json.loads((await client.get("/api/v1/bi/export", headers=setup["h_admin"],
                          params={"source_key": "leads", "format": "json"})).content)
    assert payload["total"] == 3 and len(payload["rows"]) == 3
    jobs = (await db.execute(select(ExportJob).filter(
        ExportJob.organization_id == setup["org"].id, ExportJob.kind == "download"))).scalars().all()
    assert len(jobs) == 5 and all(j.status == "success" and j.rows == 3 for j in jobs)
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id, AuditLog.action == "DATA_EXPORTED"))).scalars().all()
    assert len(audits) == 5


@pytest.mark.asyncio
async def test_report_export(client: AsyncClient, setup):
    r = await client.get("/api/v1/bi/export", headers=setup["h_admin"],
                         params={"source_type": "report", "source_key": setup["report_id"], "format": "csv"})
    assert r.status_code == 200
    assert "status" in r.text.splitlines()[0]


@pytest.mark.asyncio
async def test_webhook_export_success_and_failure(client: AsyncClient, setup, monkeypatch, db: AsyncSession):
    calls = []
    async def ok(self, url, fmt, res, name):
        calls.append((url, fmt, res["total"]))
        return True, None
    monkeypatch.setattr(BIExportService, "_post_webhook", ok)
    r = await client.post("/api/v1/bi/export/webhook", headers=setup["h_admin"], json={
        "source_key": "leads", "url": "https://warehouse.example.com/ingest", "format": "json"})
    assert r.json()["status"] == "success" and calls[0][2] == 3

    async def bad(self, url, fmt, res, name):
        return False, "HTTP 503"
    monkeypatch.setattr(BIExportService, "_post_webhook", bad)
    r = await client.post("/api/v1/bi/export/webhook", headers=setup["h_admin"], json={
        "source_key": "leads", "url": "https://warehouse.example.com/ingest"})
    assert r.json()["status"] == "failed" and r.json()["error"] == "HTTP 503"
    kinds = (await db.execute(select(ExportJob).filter(ExportJob.kind == "webhook",
        ExportJob.organization_id == setup["org"].id))).scalars().all()
    assert {j.status for j in kinds} == {"success", "failed"}


@pytest.mark.asyncio
async def test_cloud_export_local_storage(client: AsyncClient, setup):
    import os
    r = await client.post("/api/v1/bi/export/cloud", headers=setup["h_admin"], json={
        "source_key": "leads", "format": "csv", "path_prefix": "warehouse"})
    body = r.json()
    assert body["status"] == "success", body
    assert body["target"].startswith("uploads/exports/") and "warehouse" in body["target"]
    assert os.path.exists(body["target"])
    os.remove(body["target"])


@pytest.mark.asyncio
async def test_settings_masking(client: AsyncClient, setup):
    r = await client.patch("/api/v1/bi/settings", headers=setup["h_admin"], json={
        "storage_provider": "s3", "s3_bucket": "crm-exports", "s3_access_key": "AKIA1234",
        "s3_secret_key": "supersecret"})
    body = r.json()
    assert body["storage_provider"] == "s3" and body["s3_bucket"] == "crm-exports"
    assert body["s3_access_key"] == "…1234" and body["s3_secret_key"] == "••••"
    bad = await client.patch("/api/v1/bi/settings", headers=setup["h_admin"], json={"storage_provider": "ftp"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_bi_token_feed_flow(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/bi/tokens", headers=setup["h_admin"], json={"name": "Power BI key"})
    assert r.status_code == 201
    token = r.json()["token"]
    assert len(token) > 20

    # list masks the token
    r = await client.get("/api/v1/bi/tokens", headers=setup["h_admin"])
    assert r.json()[0]["token"].startswith("…")

    # feed index + data — NO bearer auth
    r = await client.get(f"/api/v1/bi/feed/{token}")
    assert r.status_code == 200
    assert any(d["key"] == "leads" for d in r.json()["datasets"])
    r = await client.get(f"/api/v1/bi/feed/{token}/dataset/leads.json")
    assert r.status_code == 200
    assert json.loads(r.content)["total"] == 3
    r = await client.get(f"/api/v1/bi/feed/{token}/dataset/leads.csv")
    assert r.status_code == 200 and "status" in r.text.splitlines()[0]
    # report feed
    r = await client.get(f"/api/v1/bi/feed/{token}/report/{setup['report_id']}.json")
    assert r.status_code == 200 and json.loads(r.content)["total"] == 3
    # incremental: future cursor → 0 rows
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = await client.get(f"/api/v1/bi/feed/{token}/dataset/leads.json", params={"created_since": future})
    assert json.loads(r.content)["total"] == 0
    # feed access audited
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id, AuditLog.action == "BI_FEED_ACCESSED"))).scalars().all()
    assert len(audits) >= 4


@pytest.mark.asyncio
async def test_token_scoping_rotation_and_revocation(client: AsyncClient, setup):
    r = await client.post("/api/v1/bi/tokens", headers=setup["h_admin"],
                          json={"name": "Contacts only", "datasets": ["contacts"]})
    tid, token = r.json()["id"], r.json()["token"]
    r = await client.get(f"/api/v1/bi/feed/{token}/dataset/leads.json")
    assert r.status_code == 403  # dataset not in scope
    r = await client.get(f"/api/v1/bi/feed/{token}/dataset/contacts.json")
    assert r.status_code == 200

    r = await client.post(f"/api/v1/bi/tokens/{tid}/rotate", headers=setup["h_admin"])
    new_token = r.json()["token"]
    assert new_token != token
    assert (await client.get(f"/api/v1/bi/feed/{token}/dataset/contacts.json")).status_code == 404
    assert (await client.get(f"/api/v1/bi/feed/{new_token}/dataset/contacts.json")).status_code == 200

    await client.patch(f"/api/v1/bi/tokens/{tid}", headers=setup["h_admin"], json={"is_active": False})
    assert (await client.get(f"/api/v1/bi/feed/{new_token}/dataset/contacts.json")).status_code == 404
    assert (await client.get("/api/v1/bi/feed/not-a-token")).status_code == 404


@pytest.mark.asyncio
async def test_data_sync_run_and_incremental_cursor(client: AsyncClient, setup, monkeypatch, db: AsyncSession):
    async def ok(self, url, fmt, res, name):
        return True, None
    monkeypatch.setattr(BIExportService, "_post_webhook", ok)
    r = await client.post("/api/v1/bi/syncs", headers=setup["h_admin"], json={
        "name": "Warehouse sync", "source_key": "leads", "destination": "webhook",
        "target_url": "https://wh.example.com/ingest", "mode": "incremental", "frequency": "daily"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["last_cursor"] is None

    r = await client.post(f"/api/v1/bi/syncs/{sid}/run", headers=setup["h_admin"])
    assert r.json()["status"] == "success" and r.json()["rows"] == 3
    r = await client.get("/api/v1/bi/syncs", headers=setup["h_admin"])
    row = next(x for x in r.json() if x["id"] == sid)
    assert row["last_cursor"] is not None and row["run_count"] == 1 and row["last_status"] == "success"

    # second incremental run: cursor is now → 0 new rows
    r = await client.post(f"/api/v1/bi/syncs/{sid}/run", headers=setup["h_admin"])
    assert r.json()["status"] == "success" and r.json()["rows"] == 0

    # webhook sync without URL rejected
    bad = await client.post("/api/v1/bi/syncs", headers=setup["h_admin"], json={
        "name": "x", "source_key": "leads", "destination": "webhook"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_sync_scan_advances(client: AsyncClient, setup, monkeypatch, db: AsyncSession):
    async def ok(self, url, fmt, res, name):
        return True, None
    monkeypatch.setattr(BIExportService, "_post_webhook", ok)
    r = await client.post("/api/v1/bi/syncs", headers=setup["h_admin"], json={
        "name": "Due sync", "source_key": "leads", "destination": "webhook",
        "target_url": "https://wh.example.com/i", "frequency": "weekly"})
    sid = uuid.UUID(r.json()["id"])
    c = (await db.execute(select(BISyncConfig).filter(BISyncConfig.id == sid))).scalars().first()
    c.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(c); await db.commit()
    out = await BIExportService(db).scan(setup["org"].id)
    await db.commit()
    assert out["synced"] == 1 and out["failed"] == 0
    await db.refresh(c)
    nxt = c.next_run_at if c.next_run_at.tzinfo else c.next_run_at.replace(tzinfo=timezone.utc)
    assert nxt > datetime.now(timezone.utc) and c.last_status == "success"


@pytest.mark.asyncio
async def test_history_and_dashboard(client: AsyncClient, setup):
    await client.get("/api/v1/bi/export", headers=setup["h_admin"],
                     params={"source_key": "leads", "format": "csv"})
    r = await client.get("/api/v1/bi/history", headers=setup["h_admin"])
    assert len(r.json()) >= 1 and r.json()[0]["kind"] == "download"
    r = await client.get("/api/v1/bi/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["exports"] >= 1 and d["by_kind"]["download"] >= 1 and "success_rate" in d


@pytest.mark.asyncio
async def test_employee_forbidden(client: AsyncClient, setup):
    assert (await client.get("/api/v1/bi/export", headers=setup["h_emp"],
                             params={"source_key": "leads", "format": "csv"})).status_code == 403
    assert (await client.get("/api/v1/bi/tokens", headers=setup["h_emp"])).status_code == 403
    assert (await client.post("/api/v1/bi/tokens", headers=setup["h_emp"],
                              json={"name": "x"})).status_code == 403

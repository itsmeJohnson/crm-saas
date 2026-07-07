import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.report_builder import ReportDefinition
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
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Rep Org", "slug": "rep-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@rep.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@rep.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    # 3 leads: 2 New (200 + 300), 1 Contacted (500) — drives grouping/aggregation
    for st, val in [("New", 200), ("New", 300), ("Contacted", 500)]:
        db.add(Lead(organization_id=org.id, last_name="L", title="t", status=st, value=val, source="Website",
                    created_by=admin.id, assigned_user_id=admin.id, stage_id=stage.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_permissions_and_preview_engine(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/report-builder/catalog", headers=d["h_admin"])).json()
    keys = {ds["key"] for ds in cat["datasets"]}
    assert {"leads", "invoices", "tasks"} <= keys and "sum" in cat["aggregations"]
    lead_cols = {c["field"] for ds in cat["datasets"] if ds["key"] == "leads" for c in ds["columns"]}
    assert "owner.first_name" in lead_cols  # a JOIN column is exposed
    # employees cannot use the builder
    assert (await client.post("/api/v1/report-builder/preview", json={
        "name": "x", "dataset": "leads", "columns": [{"field": "status"}]}, headers=d["h_emp"])).status_code == 403
    # grouped + aggregated preview (columns/rows/grouping/sorting/aggregation)
    res = (await client.post("/api/v1/report-builder/preview", json={
        "name": "Leads by status", "dataset": "leads",
        "columns": [{"field": "status"}, {"field": "value", "agg": "sum"}],
        "group_by": ["status"], "sort": [{"field": "value", "dir": "desc"}]}, headers=d["h_admin"])).json()
    rows = {r["status"]: r["sum__value"] for r in res["rows"]}
    assert rows == {"New": 500.0, "Contacted": 500.0} and res["total"] == 2
    assert res["rows"][0]["sum__value"] >= res["rows"][1]["sum__value"]  # sorted desc


@pytest.mark.asyncio
async def test_filtering_calculated_fields_and_joins(client: AsyncClient, setup: dict):
    d = setup
    # filter (status = New) + calculated field + join column
    res = (await client.post("/api/v1/report-builder/preview", json={
        "name": "New leads", "dataset": "leads",
        "columns": [{"field": "status"}, {"field": "value"}, {"field": "owner.first_name"}, {"field": "doubled"}],
        "filters": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "status", "op": "eq", "value": "New"}]},
        "calculated_fields": [{"name": "doubled", "expression": "value * 2", "type": "number"}]}, headers=d["h_admin"])).json()
    assert res["total"] == 2
    assert all(r["status"] == "New" and r["owner.first_name"] == "Ad" for r in res["rows"])
    assert all(r["doubled"] == r["value"] * 2 for r in res["rows"])
    # an unsafe calculated expression is rejected
    bad = await client.post("/api/v1/report-builder/preview", json={
        "name": "bad", "dataset": "leads", "columns": [{"field": "value"}, {"field": "x"}],
        "calculated_fields": [{"name": "x", "expression": "__import__('os').system('x')", "type": "number"}]}, headers=d["h_admin"])
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_pivot_report(client: AsyncClient, setup: dict):
    d = setup
    res = (await client.post("/api/v1/report-builder/preview", json={
        "name": "pivot", "dataset": "leads", "columns": [{"field": "status"}],
        "pivot": {"row": "source", "col": "status", "measure": "value", "agg": "sum"}}, headers=d["h_admin"])).json()
    piv = res["pivot"]
    assert piv["row_field"] == "source" and "New" in piv["columns"] and "Contacted" in piv["columns"]
    website = next(r for r in piv["rows"] if r["__row"] == "Website")
    assert website["New"] == 500.0 and website["Contacted"] == 500.0


@pytest.mark.asyncio
async def test_saved_shared_versioned_scheduled_and_export(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    r = (await client.post("/api/v1/report-builder", json={
        "name": "My report", "dataset": "leads", "columns": [{"field": "status"}, {"field": "value"}],
        "visibility": "organization"}, headers=d["h_admin"])).json()
    assert r["visibility"] == "organization" and r["version"] == 1
    # run a saved report
    run = (await client.get(f"/api/v1/report-builder/{r['id']}/run", headers=d["h_admin"])).json()
    assert run["total"] == 3
    # shared box surfaces org-visible reports to another manager? (admin sees own via mine)
    mine = (await client.get("/api/v1/report-builder", params={"box": "mine"}, headers=d["h_admin"])).json()
    assert any(x["id"] == r["id"] for x in mine)
    # update → new version snapshot
    await client.patch(f"/api/v1/report-builder/{r['id']}", json={"columns": [{"field": "status"}]}, headers=d["h_admin"])
    versions = (await client.get(f"/api/v1/report-builder/{r['id']}/versions", headers=d["h_admin"])).json()
    assert len(versions) >= 2
    restored = (await client.post(f"/api/v1/report-builder/{r['id']}/versions/restore",
                json={"version_no": min(v["version_no"] for v in versions)}, headers=d["h_admin"])).json()
    assert len(restored["columns"]) == 2  # original two columns back
    # schedule it
    sched = (await client.patch(f"/api/v1/report-builder/{r['id']}/schedule",
             json={"schedule_frequency": "daily", "schedule_recipients": [str(d["emp"].id)]}, headers=d["h_admin"])).json()
    assert sched["schedule_frequency"] == "daily" and sched["next_run"] is not None
    # export CSV
    exp = await client.get(f"/api/v1/report-builder/{r['id']}/export", headers=d["h_admin"])
    assert exp.status_code == 200 and "status" in exp.text


@pytest.mark.asyncio
async def test_templates_and_dashboard_pin(client: AsyncClient, setup: dict):
    d = setup
    seeded = (await client.post("/api/v1/report-builder/templates/seed", json={}, headers=d["h_admin"])).json()
    assert seeded["created"] >= 1
    tpls = (await client.get("/api/v1/report-builder/templates", headers=d["h_admin"])).json()
    inst = (await client.post(f"/api/v1/report-builder/templates/{tpls[0]['id']}/instantiate", headers=d["h_admin"])).json()
    assert inst["is_template"] is False
    # pin a report to the dashboard
    r = (await client.post("/api/v1/report-builder", json={
        "name": "Pinned", "dataset": "leads", "columns": [{"field": "status"}, {"field": "value", "agg": "sum"}],
        "group_by": ["status"], "pinned_to_dashboard": True}, headers=d["h_admin"])).json()
    dash = (await client.get("/api/v1/report-builder/dashboard", headers=d["h_admin"])).json()
    assert any(c["id"] == r["id"] and c["total"] >= 1 for c in dash["reports"])

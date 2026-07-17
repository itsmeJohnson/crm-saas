import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
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
    org = await OrganizationRepository(db).create({"name": "Viz Org", "slug": "viz-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@viz.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@viz.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)

    def lead(status, value, pin, days_ago):
        return Lead(organization_id=org.id, last_name="L", title="t", status=status, value=value,
                    pin_code=pin, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
                    created_at=now - timedelta(days=days_ago))

    # 4 New (recent), 2 Contacted, 1 Converted (recent), 2 New (previous window ~40d ago)
    db.add_all([
        lead("New", 100, "110001", 5), lead("New", 200, "110002", 6),
        lead("New", 300, "560001", 7), lead("New", 400, "560002", 8),
        lead("Contacted", 500, "400001", 9), lead("Contacted", 600, "400002", 10),
        lead("Converted", 1000, "700001", 4),
        lead("New", 700, "110003", 40), lead("New", 800, "110004", 45),
    ])
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog(client: AsyncClient, setup):
    r = await client.get("/api/v1/visualizations/catalog", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    keys = [v["key"] for v in body["viz_types"]]
    for k in ("bar", "pivot", "heatmap", "geo", "treemap", "funnel", "gauge", "timeline", "comparison"):
        assert k in keys
    assert any(d["key"] == "leads" for d in body["datasets"])


@pytest.mark.asyncio
async def test_bar_render_counts_by_status(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "bar", "dataset": "leads", "config": {"dimension": "status"}})
    assert r.status_code == 200, r.text
    pts = {p["label"]: p["value"] for p in r.json()["data"]["points"]}
    assert pts == {"New": 6, "Contacted": 2, "Converted": 1}


@pytest.mark.asyncio
async def test_line_render_with_sum_measure(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "line", "dataset": "leads",
        "config": {"dimension": "status", "measure": {"field": "value", "agg": "sum"}}})
    pts = {p["label"]: p["value"] for p in r.json()["data"]["points"]}
    assert pts["Contacted"] == 1100 and pts["Converted"] == 1000


@pytest.mark.asyncio
async def test_table_render(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "table", "dataset": "leads", "config": {"columns": ["status", "value"], "limit": 5}})
    d = r.json()["data"]
    assert d["total"] == 9 and len(d["rows"]) == 5


@pytest.mark.asyncio
async def test_pivot_and_heatmap(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "pivot", "dataset": "leads", "config": {"row": "status", "col": "priority"}})
    assert r.status_code == 200
    assert r.json()["data"]["row_field"] == "status"
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "heatmap", "dataset": "leads",
        "config": {"row": "status", "col": "city", "measure": {"agg": "count"}}})
    d = r.json()["data"]
    assert set(d["rows"]) == {"New", "Contacted", "Converted"}
    assert d["max"] >= 1 and len(d["cells"]) == len(d["rows"])


@pytest.mark.asyncio
async def test_treemap(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "treemap", "dataset": "leads",
        "config": {"dimension": "status", "measure": {"field": "value", "agg": "sum"}}})
    nodes = {n["name"]: n["value"] for n in r.json()["data"]["nodes"]}
    assert nodes["New"] == 2500 and nodes["Converted"] == 1000


@pytest.mark.asyncio
async def test_funnel_with_ordered_stages(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "funnel", "dataset": "leads",
        "config": {"dimension": "status", "stages": ["New", "Contacted", "Converted"]}})
    stages = r.json()["data"]["stages"]
    assert [s["label"] for s in stages] == ["New", "Contacted", "Converted"]
    assert stages[0]["value"] == 6 and stages[0]["pct_of_first"] == 100.0
    assert stages[1]["drop_pct"] > 0


@pytest.mark.asyncio
async def test_gauge(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "gauge", "dataset": "leads",
        "config": {"target": 5000, "measure": {"field": "value", "agg": "sum"}}})
    d = r.json()["data"]
    assert d["value"] == 4600 and d["target"] == 5000 and d["pct"] == 92.0


@pytest.mark.asyncio
async def test_timeline_buckets(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "timeline", "dataset": "leads",
        "config": {"date_field": "created_at", "interval": "day"}})
    d = r.json()["data"]
    assert d["interval"] == "day"
    assert sum(p["value"] for p in d["points"]) == 9
    assert len(d["points"]) == 9  # every lead created on a distinct day


@pytest.mark.asyncio
async def test_comparison_windows(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "comparison", "dataset": "leads",
        "config": {"date_field": "created_at", "window_days": 30, "dimension": "status"}})
    d = r.json()["data"]
    assert d["current"] == 7 and d["previous"] == 2
    by = {r["label"]: r for r in d["by_dimension"]}
    assert by["New"]["current"] == 4 and by["New"]["previous"] == 2


@pytest.mark.asyncio
async def test_geo_pin_zones(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "geo", "dataset": "leads", "config": {"field": "pin_code"}})
    regions = {x["region"]: x["value"] for x in r.json()["data"]["regions"]}
    assert regions["North (Delhi, Haryana, Punjab, HP, J&K)"] == 4  # 110xxx
    assert regions["AP, Telangana & Karnataka"] == 2  # 560xxx
    assert regions["Maharashtra, MP & Goa"] == 2  # 400xxx
    assert regions["WB, Odisha & North-East"] == 1  # 700xxx


@pytest.mark.asyncio
async def test_drilldown_rows(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/drilldown", headers=setup["h_admin"], json={
        "dataset": "leads", "field": "status", "value": "Contacted"})
    d = r.json()
    assert d["total"] == 2 and all(row["status"] == "Contacted" for row in d["rows"])


@pytest.mark.asyncio
async def test_saved_crud_pin_dashboard_export(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations", headers=setup["h_admin"], json={
        "name": "Leads by status", "viz_type": "bar", "dataset": "leads",
        "config": {"dimension": "status"}, "is_pinned": True})
    assert r.status_code == 201, r.text
    vid = r.json()["id"]

    r = await client.get("/api/v1/visualizations", headers=setup["h_admin"])
    assert any(v["id"] == vid for v in r.json())

    r = await client.get(f"/api/v1/visualizations/{vid}/data", headers=setup["h_admin"])
    assert r.status_code == 200 and len(r.json()["data"]["points"]) == 3

    r = await client.get("/api/v1/visualizations/dashboard", headers=setup["h_admin"])
    assert r.status_code == 200
    cards = r.json()["pinned"]
    assert any(c["id"] == vid and c["data"] for c in cards)

    r = await client.get(f"/api/v1/visualizations/{vid}/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "label,value" in r.text and "New,6" in r.text

    r = await client.patch(f"/api/v1/visualizations/{vid}", headers=setup["h_admin"],
                           json={"name": "Renamed", "is_pinned": False})
    assert r.json()["name"] == "Renamed" and r.json()["is_pinned"] is False

    r = await client.delete(f"/api/v1/visualizations/{vid}", headers=setup["h_admin"])
    assert r.status_code == 204
    r = await client.get(f"/api/v1/visualizations/{vid}/data", headers=setup["h_admin"])
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_private_visibility(client: AsyncClient, setup, db: AsyncSession):
    # a private viz of the admin is invisible to another manager-level user? —
    # employees can't use the engine at all; verify a second admin can't see private
    ur = UserRepository(db)
    admin2 = await ur.create_user(setup["org"].id, {"email": "admin2@viz.com",
        "hashed_password": get_password_hash("password123"), "first_name": "Ad2", "last_name": "Min",
        "role": "OrgAdmin", "is_active": True})
    await db.commit()
    h2 = {"Authorization": f"Bearer {create_access_token(admin2.id)}"}
    r = await client.post("/api/v1/visualizations", headers=setup["h_admin"], json={
        "name": "Secret", "viz_type": "pie", "dataset": "leads",
        "config": {"dimension": "status"}, "visibility": "private"})
    vid = r.json()["id"]
    r = await client.get("/api/v1/visualizations", headers=h2)
    assert all(v["id"] != vid for v in r.json())
    r = await client.get(f"/api/v1/visualizations/{vid}/data", headers=h2)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_employee_forbidden(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_emp"], json={
        "viz_type": "bar", "dataset": "leads", "config": {"dimension": "status"}})
    assert r.status_code == 403
    r = await client.post("/api/v1/visualizations", headers=setup["h_emp"], json={
        "name": "x", "viz_type": "bar", "dataset": "leads", "config": {"dimension": "status"}})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_invalid_specs_rejected(client: AsyncClient, setup):
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "sparkle", "dataset": "leads", "config": {}})
    assert r.status_code == 400
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "bar", "dataset": "leads", "config": {}})
    assert r.status_code == 400  # missing dimension
    r = await client.post("/api/v1/visualizations/render", headers=setup["h_admin"], json={
        "viz_type": "bar", "dataset": "unicorns", "config": {"dimension": "status"}})
    assert r.status_code == 400

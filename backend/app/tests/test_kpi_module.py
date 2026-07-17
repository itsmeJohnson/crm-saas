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
from app.models.kpi import KPIAlert
from app.models.notification import Notification
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
    org = await OrganizationRepository(db).create({"name": "KPI Org", "slug": "kpi-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@kpi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@kpi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    # 4 leads, 1 converted -> conversion_rate 25%
    db.add(Lead(organization_id=org.id, last_name="A", title="t", status="Converted", value=1000,
                converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    for i in range(3):
        db.add(Lead(organization_id=org.id, last_name="B", title="t", status="New", value=500,
                    assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_crud_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/kpi/catalog", headers=d["h_admin"])).json()
    keys = {m["key"] for m in cat["metrics"]}
    cats = {m["category"] for m in cat["metrics"]}
    # metrics span every domain in the checklist
    assert {"sales_conversion_rate", "mrr", "comm_delivery_rate", "workflow_success_rate", "sla_compliance",
            "avg_productivity", "pipeline_value", "department_count", "team_count", "manual"} <= keys
    assert {"sales", "financial", "communication", "workflow", "automation", "employee", "pipeline",
            "department", "team", "custom"} <= cats
    # employee cannot create a KPI
    assert (await client.post("/api/v1/kpi", json={"name": "x", "metric": "manual", "target_value": 1}, headers=d["h_emp"])).status_code == 403
    k = (await client.post("/api/v1/kpi", json={
        "name": "Conversion", "metric": "sales_conversion_rate", "target_value": 40,
        "warning_value": 30, "critical_value": 20}, headers=d["h_admin"])).json()
    assert k["category"] == "sales" and k["unit"] == "percent" and k["comparison"] == "higher_better"
    # unknown metric rejected
    assert (await client.post("/api/v1/kpi", json={"name": "bad", "metric": "ghost"}, headers=d["h_admin"])).status_code == 400
    lst = (await client.get("/api/v1/kpi", headers=d["h_admin"])).json()
    assert any(x["id"] == k["id"] for x in lst)


@pytest.mark.asyncio
async def test_evaluation_thresholds_and_manual(client: AsyncClient, setup: dict):
    d = setup
    # conversion is 25% -> between critical(20) and warning(30) => warning
    k = (await client.post("/api/v1/kpi", json={
        "name": "Conversion", "metric": "sales_conversion_rate", "target_value": 40,
        "warning_value": 30, "critical_value": 20}, headers=d["h_admin"])).json()
    ev = (await client.get(f"/api/v1/kpi/{k['id']}/evaluate", headers=d["h_admin"])).json()
    assert ev["value"] == 25.0 and ev["status"] == "warning"
    # a manual KPI reads its stored value; lower_better critical
    m = (await client.post("/api/v1/kpi", json={
        "name": "Complaints", "metric": "manual", "comparison": "lower_better", "unit": "count",
        "target_value": 5, "warning_value": 10, "critical_value": 20, "manual_value": 25}, headers=d["h_admin"])).json()
    mev = (await client.get(f"/api/v1/kpi/{m['id']}/evaluate", headers=d["h_admin"])).json()
    assert mev["value"] == 25.0 and mev["status"] == "critical"


@pytest.mark.asyncio
async def test_dashboard_report_alerts_and_notifications(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # a KPI that will breach (critical): win rate target very high
    await client.post("/api/v1/kpi", json={
        "name": "Conversion floor", "metric": "sales_conversion_rate", "target_value": 90,
        "warning_value": 80, "critical_value": 50, "notify": True}, headers=d["h_admin"])
    dash = (await client.get("/api/v1/kpi/dashboard", headers=d["h_admin"])).json()
    assert dash["summary"]["total"] >= 1 and "sales" in dash["by_category"]
    # run evaluation -> raises an alert + notifies the admin
    out = (await client.post("/api/v1/kpi/evaluate", json={}, headers=d["h_admin"])).json()
    assert out["raised"] >= 1
    alerts = (await client.get("/api/v1/kpi/alerts", params={"resolved": False}, headers=d["h_admin"])).json()
    assert len(alerts) >= 1 and alerts[0]["status"] in ("warning", "critical")
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == d["admin"].id, Notification.category == "kpi"))).scalars().first() is not None
    # re-running is idempotent (no duplicate open alert)
    out2 = (await client.post("/api/v1/kpi/evaluate", json={}, headers=d["h_admin"])).json()
    assert out2["raised"] == 0
    # resolve the alert
    r = await client.post(f"/api/v1/kpi/alerts/{alerts[0]['id']}/resolve", headers=d["h_admin"])
    assert r.status_code == 200 and r.json()["resolved"] is True
    rep = (await client.get("/api/v1/kpi/report", headers=d["h_admin"])).json()
    assert "summary" in rep and "by_category" in rep

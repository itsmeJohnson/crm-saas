import pytest
from datetime import date, datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.history import MetricSnapshot
from app.services.historical_analytics_service import (
    HistoricalAnalyticsService, _period_window, _previous_ref)
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Hist Org", "slug": "hist-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@hist.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@hist.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    db.add(Lead(organization_id=org.id, last_name="A", title="t", status="Converted", value=1000,
                converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    db.add(Lead(organization_id=org.id, last_name="B", title="t", status="New", value=500,
                assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def _seed(db, org_id, metric, day, value, granularity="daily"):
    db.add(MetricSnapshot(organization_id=org_id, snapshot_date=day, metric=metric,
                          value=value, granularity=granularity))


@pytest.mark.asyncio
async def test_meta(client: AsyncClient, setup):
    r = await client.get("/api/v1/historical-analytics/meta", headers=setup["h_admin"])
    body = r.json()
    keys = [m["key"] for m in body["metrics"]]
    assert "sales_revenue" in keys and "manual" not in keys
    assert body["comparison_periods"] == ["month", "quarter", "year"]
    assert 30 in body["rolling_windows"]


@pytest.mark.asyncio
async def test_capture_now_idempotent(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/historical-analytics/capture", headers=setup["h_admin"])
    assert r.status_code == 200
    first = r.json()["captured"]
    assert first > 5  # cross-domain snapshot captured many metrics
    r = await client.post("/api/v1/historical-analytics/capture", headers=setup["h_admin"])
    assert r.json()["captured"] == first  # same day → updated, not duplicated
    rows = (await db.execute(select(MetricSnapshot).filter(
        MetricSnapshot.organization_id == setup["org"].id))).scalars().all()
    assert len(rows) == first
    # live lead data flowed into the snapshot (2 leads, 1 converted → 50%)
    conv = next(x for x in rows if x.metric == "sales_conversion_rate")
    assert float(conv.value) == 50.0


@pytest.mark.asyncio
async def test_trends_series_and_change(client: AsyncClient, setup, db: AsyncSession):
    today = date.today()
    for i, v in enumerate([100, 110, 120, 150]):
        _seed(db, setup["org"].id, "sales_revenue", today - timedelta(days=3 - i), v)
    await db.commit()
    r = await client.get("/api/v1/historical-analytics/trends", headers=setup["h_admin"],
                         params={"metric": "sales_revenue", "days": 30})
    t = r.json()
    assert [p["value"] for p in t["points"]] == [100, 110, 120, 150]
    assert t["latest"] == 150 and t["min"] == 100 and t["max"] == 150
    assert t["change_pct"] == 50.0
    bad = await client.get("/api/v1/historical-analytics/trends", headers=setup["h_admin"],
                           params={"metric": "nope"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_monthly_quarterly_yearly_comparison(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"].id
    today = date.today()
    for period in ("month", "quarter", "year"):
        cur_start, _ = _period_window(period, today)
        prev_start, _ = _period_window(period, _previous_ref(period, today))
        metric = f"mrr"
        # clean per-iteration not needed: different dates per period may collide on month/quarter;
        # use distinct metrics per period instead
        metric = {"month": "mrr", "quarter": "arr", "year": "headcount"}[period]
        _seed(db, org, metric, cur_start, 200)
        _seed(db, org, metric, prev_start, 100)
    await db.commit()
    for period, metric in (("month", "mrr"), ("quarter", "arr"), ("year", "headcount")):
        r = await client.get("/api/v1/historical-analytics/comparison", headers=setup["h_admin"],
                             params={"period": period})
        body = r.json()
        row = next(x for x in body["rows"] if x["metric"] == metric)
        assert row["current"] == 200 and row["previous"] == 100
        assert row["change_pct"] == 100.0 and row["improved"] is True
    bad = await client.get("/api/v1/historical-analytics/comparison", headers=setup["h_admin"],
                           params={"period": "decade"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_rolling_report(client: AsyncClient, setup, db: AsyncSession):
    today = date.today()
    for i in range(10):
        _seed(db, setup["org"].id, "open_deals", today - timedelta(days=9 - i), i + 1)  # 1..10
    await db.commit()
    r = await client.get("/api/v1/historical-analytics/rolling", headers=setup["h_admin"],
                         params={"metric": "open_deals", "window": 7, "days": 30})
    pts = r.json()["points"]
    assert pts[-1]["value"] == 10
    assert pts[-1]["rolling_avg"] == 7.0  # mean of 4..10
    bad = await client.get("/api/v1/historical-analytics/rolling", headers=setup["h_admin"],
                           params={"metric": "open_deals", "window": 13})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_retention_archives_and_prunes(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"].id
    old_month = (date.today() - timedelta(days=900)).replace(day=1)
    for d, v in ((old_month, 100), (old_month + timedelta(days=1), 200)):
        _seed(db, org, "sales_revenue", d, v)
    _seed(db, org, "sales_revenue", date.today(), 500)  # recent — must survive
    await db.commit()

    out = await HistoricalAnalyticsService(db).apply_retention(org)
    await db.commit()
    assert out["pruned"] == 2 and out["archived_months"] == 1
    rows = (await db.execute(select(MetricSnapshot).filter(
        MetricSnapshot.organization_id == org, MetricSnapshot.metric == "sales_revenue"))).scalars().all()
    monthly = [r for r in rows if r.granularity == "monthly"]
    daily = [r for r in rows if r.granularity == "daily"]
    assert len(monthly) == 1 and float(monthly[0].value) == 150.0  # avg(100, 200)
    assert monthly[0].snapshot_date == old_month
    assert len(daily) == 1 and float(daily[0].value) == 500.0


@pytest.mark.asyncio
async def test_settings_and_validation(client: AsyncClient, setup):
    r = await client.get("/api/v1/historical-analytics/settings", headers=setup["h_admin"])
    assert r.json() == {"retention_days": 730, "archive_enabled": True, "capture_enabled": True}
    r = await client.patch("/api/v1/historical-analytics/settings", headers=setup["h_admin"],
                           json={"retention_days": 365, "archive_enabled": False})
    assert r.json()["retention_days"] == 365 and r.json()["archive_enabled"] is False
    bad = await client.patch("/api/v1/historical-analytics/settings", headers=setup["h_admin"],
                             json={"retention_days": 5})
    assert bad.status_code == 422  # pydantic ge=30


@pytest.mark.asyncio
async def test_dashboard_and_report(client: AsyncClient, setup, db: AsyncSession):
    await client.post("/api/v1/historical-analytics/capture", headers=setup["h_admin"])
    r = await client.get("/api/v1/historical-analytics/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["days_covered"] >= 1 and d["metrics_tracked"] > 5
    assert d["last_capture"] == date.today().isoformat()
    assert "sales_revenue" in d["sparklines"] and d["settings"]["retention_days"] == 730
    r = await client.get("/api/v1/historical-analytics/report", headers=setup["h_admin"],
                         params={"period": "month"})
    body = r.json()
    assert "improved" in body and "declined" in body and body["period"] == "month"


@pytest.mark.asyncio
async def test_exports(client: AsyncClient, setup, db: AsyncSession):
    today = date.today()
    _seed(db, setup["org"].id, "sales_revenue", today, 999)
    await db.commit()
    r = await client.get("/api/v1/historical-analytics/export", headers=setup["h_admin"],
                         params={"kind": "trend", "metric": "sales_revenue", "days": 30})
    assert "date,metric,value,granularity" in r.text and "999" in r.text
    r = await client.get("/api/v1/historical-analytics/export", headers=setup["h_admin"],
                         params={"kind": "comparison", "period": "month"})
    assert r.text.startswith("metric,label,current,previous")
    r = await client.get("/api/v1/historical-analytics/export", headers=setup["h_admin"],
                         params={"kind": "snapshots"})
    assert "sales_revenue" in r.text


@pytest.mark.asyncio
async def test_warehouse_ready_via_report_builder_and_bi(client: AsyncClient, setup, db: AsyncSession):
    await client.post("/api/v1/historical-analytics/capture", headers=setup["h_admin"])
    # metric_history is a first-class report-builder dataset…
    r = await client.get("/api/v1/report-builder/catalog", headers=setup["h_admin"])
    assert any(d["key"] == "metric_history" for d in r.json()["datasets"])
    # …queryable through the engine…
    r = await client.post("/api/v1/report-builder/preview", headers=setup["h_admin"], json={
        "name": "hist", "dataset": "metric_history",
        "columns": [{"field": "metric"}, {"field": "value"}, {"field": "snapshot_date"}]})
    assert r.status_code == 200 and r.json()["total"] > 5
    # …and exportable through the BI layer (warehouse ready).
    r = await client.get("/api/v1/bi/export", headers=setup["h_admin"],
                         params={"source_key": "metric_history", "format": "json"})
    assert r.status_code == 200
    import json as _json
    assert _json.loads(r.content)["total"] > 5


@pytest.mark.asyncio
async def test_employee_forbidden(client: AsyncClient, setup):
    for path in ("/api/v1/historical-analytics/dashboard", "/api/v1/historical-analytics/settings"):
        assert (await client.get(path, headers=setup["h_emp"])).status_code == 403
    assert (await client.post("/api/v1/historical-analytics/capture",
                              headers=setup["h_emp"])).status_code == 403

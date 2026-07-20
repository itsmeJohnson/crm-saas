import pytest
from datetime import datetime, date, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.company import Company
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
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
    org = await OrganizationRepository(db).create({"name": "Fcast Org", "slug": "fcast-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@fc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@fc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(__import__("sqlalchemy").select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    cust = Company(organization_id=org.id, name="Acme", company_type="Customer", created_by=admin.id)
    db.add(cust); await db.flush()

    # upward revenue: 3 monthly invoices 100 / 200 / 300 (older -> newer)
    for months_ago, tot in [(2, 100), (1, 200), (0, 300)]:
        inv = CustomerInvoice(organization_id=org.id, company_id=cust.id, invoice_number=f"I{months_ago}",
                              status="Sent", subtotal=tot, total_amount=tot, created_by=admin.id)
        inv.created_at = now - timedelta(days=30 * months_ago + 1)
        db.add(inv)
    # a payment (collections) + open pipeline leads + one converted (sales/conversion)
    op1 = Lead(organization_id=org.id, last_name="A", title="t", status="New", value=5000,
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    op2 = Lead(organization_id=org.id, last_name="B", title="t", status="New", value=3000,
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    conv = Lead(organization_id=org.id, last_name="C", title="t", status="Converted", value=2000,
                converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add_all([op1, op2, conv])
    await db.flush()
    inv2 = (await db.execute(__import__("sqlalchemy").select(CustomerInvoice).filter(
        CustomerInvoice.invoice_number == "I0"))).scalars().first()
    db.add(CustomerPayment(organization_id=org.id, company_id=cust.id, invoice_id=inv2.id, amount=300,
                           method="Card", created_by=admin.id, paid_at=now))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_forecast_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/forecasting/catalog", headers=d["h_admin"])).json()
    assert "revenue" in cat["metrics"] and "linear" in cat["methods"] and "monthly" in cat["granularities"]
    assert (await client.get("/api/v1/forecasting/forecast", headers=d["h_emp"])).status_code == 403
    # revenue forecast: upward history -> "up" trend, N forecast points
    f = (await client.get("/api/v1/forecasting/forecast",
         params={"metric": "revenue", "periods": 4, "method": "linear", "granularity": "monthly"}, headers=d["h_admin"])).json()
    assert f["metric"] == "revenue" and f["method"] == "linear" and len(f["forecast"]) == 4
    assert f["trend"]["direction"] == "up" and f["total_forecast"] > 0
    assert all("lower" in p and "upper" in p and p["upper"] >= p["value"] >= p["lower"] for p in f["forecast"])
    # bad params rejected
    assert (await client.get("/api/v1/forecasting/forecast", params={"metric": "bogus"}, headers=d["h_admin"])).status_code == 400
    assert (await client.get("/api/v1/forecasting/forecast", params={"method": "magic"}, headers=d["h_admin"])).status_code == 400


@pytest.mark.asyncio
async def test_scenario_seasonality_trend_and_historical(client: AsyncClient, setup: dict):
    d = setup
    sc = (await client.get("/api/v1/forecasting/scenario", params={"metric": "revenue", "periods": 3}, headers=d["h_admin"])).json()
    s = sc["scenarios"]
    assert s["optimistic"]["total"] >= s["base"]["total"] >= s["pessimistic"]["total"]
    assert s["optimistic"]["factor"] == 1.15 and s["pessimistic"]["factor"] == 0.85
    seas = (await client.get("/api/v1/forecasting/seasonality", params={"metric": "revenue", "granularity": "monthly"}, headers=d["h_admin"])).json()
    assert len(seas["indices"]) == 12 and seas["peak"] is not None
    tr = (await client.get("/api/v1/forecasting/trend", params={"metric": "leads"}, headers=d["h_admin"])).json()
    assert "direction" in tr and "growth_rate" in tr and "history" in tr
    hc = (await client.get("/api/v1/forecasting/historical-comparison", params={"metric": "revenue", "holdout": 2}, headers=d["h_admin"])).json()
    assert "accuracy" in hc and "mape" in hc  # may be None if insufficient history, but keys present


@pytest.mark.asyncio
async def test_pipeline_goals_dashboard_export(client: AsyncClient, setup: dict):
    d = setup
    pf = (await client.get("/api/v1/forecasting/pipeline", params={"periods": 3}, headers=d["h_admin"])).json()
    assert pf["open_pipeline_value"] == 8000.0 and pf["conversion_rate"] > 0
    assert pf["expected_close_total"] > 0 and len(pf["forecast"]) == 3
    gf = (await client.get("/api/v1/forecasting/goals", headers=d["h_admin"])).json()
    assert "targets" in gf and "on_track" in gf and "at_risk" in gf
    dash = (await client.get("/api/v1/forecasting/dashboard", headers=d["h_admin"])).json()
    assert "revenue" in dash and "next_month" in dash["revenue"] and "pipeline_expected_close" in dash
    exp = await client.get("/api/v1/forecasting/export", params={"metric": "revenue"}, headers=d["h_admin"])
    assert exp.status_code == 200 and "revenue forecast" in exp.text and "forecast" in exp.text

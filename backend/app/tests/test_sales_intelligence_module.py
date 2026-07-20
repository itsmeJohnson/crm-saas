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
from app.models.activity import Activity
from app.models.company import Company
from app.models.customer_order import CustomerOrder
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.services.sales_intelligence_service import SalesIntelligenceService
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS", "SALES_PIPELINE"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "SI Org", "slug": "si-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@si.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@si.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    strong = Lead(organization_id=org.id, first_name="Strong", last_name="Deal", title="t", status="Qualified",
                  value=80000, score=85, priority="High", email="s@x.com", phone="+911", company_name="BigCo",
                  assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id, created_at=now - timedelta(days=4))
    stalled = Lead(organization_id=org.id, last_name="Stalled", title="t", status="New", value=5000, score=20,
                   assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id, created_at=now - timedelta(days=120))
    won = Lead(organization_id=org.id, last_name="Wonner", title="t", status="Converted", value=30000,
               converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    lost = Lead(organization_id=org.id, last_name="Loster", title="t", status="Lost", value=10000,
                lost_reason="Lost to Salesforce on price", assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add_all([strong, stalled, won, lost])
    await db.flush()
    db.add_all([
        Activity(organization_id=org.id, activity_type="Call", subject="c1", lead_id=strong.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Call", subject="c2", lead_id=strong.id,
                 assigned_user_id=admin.id, created_by=admin.id),
    ])
    # a customer with orders/payments for upsell
    cust = Company(organization_id=org.id, name="Loyal Ltd", created_by=admin.id, company_type="Customer")
    db.add(cust)
    await db.flush()
    db.add(CustomerOrder(organization_id=org.id, company_id=cust.id, order_number="O1", status="Fulfilled",
                         order_date=now - timedelta(days=15), total_amount=20000, created_by=admin.id))
    inv = CustomerInvoice(organization_id=org.id, company_id=cust.id, invoice_number="I1", status="Paid",
                          issue_date=now - timedelta(days=15), due_date=now - timedelta(days=1),
                          total_amount=20000, amount_paid=20000, created_by=admin.id)
    db.add(inv)
    await db.flush()
    db.add(CustomerPayment(organization_id=org.id, company_id=cust.id, invoice_id=inv.id, amount=20000,
                           paid_at=now - timedelta(days=10), created_by=admin.id))
    db.add(Activity(organization_id=org.id, activity_type="Call", subject="check-in", company_id=cust.id,
                    assigned_user_id=admin.id, created_by=admin.id, created_at=now - timedelta(days=5)))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "strong": strong, "stalled": stalled, "lost": lost, "cust": cust,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def test_scan_competitors():
    svc = SalesIntelligenceService.__new__(SalesIntelligenceService)
    assert "Salesforce" in svc._scan_competitors("we lost to salesforce on price")
    assert "Hubspot" in svc._scan_competitors("they are going with hubspot")
    assert svc._scan_competitors("no competitor here at all") == []


@pytest.mark.asyncio
async def test_deal_intelligence(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/sales-intelligence/deals/{setup['strong'].id}", headers=setup["h_admin"])
    b = r.json()
    assert b["win_probability"] > 55 and b["stage"] == "open"
    assert b["expected_value"] == round(80000 * b["win_probability"] / 100, 2)
    assert b["loss_risk"] == round(100 - b["win_probability"], 1)
    assert b["health"] == "strong" and any("call" in f["factor"] for f in b["win_factors"])
    # stalled deal: high sales risk, at_risk health
    r = await client.get(f"/api/v1/sales-intelligence/deals/{setup['stalled'].id}", headers=setup["h_admin"])
    b = r.json()
    assert b["sales_risk"] > 0 and b["sales_risk_reasons"]
    assert b["health"] in ("at_risk", "moderate")


@pytest.mark.asyncio
async def test_generative_endpoints(client: AsyncClient, setup):
    lid = setup["strong"].id
    r = await client.get(f"/api/v1/sales-intelligence/deals/{lid}/summary", headers=setup["h_admin"])
    assert r.status_code == 200 and "Summarize this lead" in r.json()["text"]
    r = await client.post(f"/api/v1/sales-intelligence/deals/{lid}/coaching", headers=setup["h_admin"])
    assert r.status_code == 200 and "sales coach" in r.json()["text"].lower()
    r = await client.post(f"/api/v1/sales-intelligence/deals/{lid}/objection-handling", headers=setup["h_admin"],
                          json={"objection": "Your price is too high"})
    assert r.status_code == 200 and "too high" in r.json()["text"]
    bad = await client.post(f"/api/v1/sales-intelligence/deals/{lid}/objection-handling", headers=setup["h_admin"],
                            json={"objection": "  "})
    assert bad.status_code == 400
    r = await client.post(f"/api/v1/sales-intelligence/deals/{lid}/proposal", headers=setup["h_admin"])
    assert r.status_code == 200 and "proposal" in r.json()["text"].lower()


@pytest.mark.asyncio
async def test_quotation(client: AsyncClient, setup):
    r = await client.post(f"/api/v1/sales-intelligence/deals/{setup['strong'].id}/quotation", headers=setup["h_admin"])
    b = r.json()
    assert len(b["line_items"]) == 3
    assert b["subtotal"] == round(80000 * 0.8 + 80000 * 0.15 + 80000 * 0.05, 2)
    assert b["total"] == round(b["subtotal"] + b["tax"], 2) and b["currency"] == "INR"
    assert b["cover_note"]


@pytest.mark.asyncio
async def test_competitor_analysis(client: AsyncClient, setup):
    r = await client.get("/api/v1/sales-intelligence/competitor-analysis", headers=setup["h_admin"])
    b = r.json()
    assert b["lost_to_competitor"] >= 1
    sf = next(c for c in b["competitors"] if c["competitor"] == "Salesforce")
    assert sf["lost_to"] >= 1


@pytest.mark.asyncio
async def test_upsell_cross_sell(client: AsyncClient, setup):
    r = await client.get("/api/v1/sales-intelligence/upsell", headers=setup["h_admin"])
    b = r.json()
    assert any(u["customer_id"] == str(setup["cust"].id) for u in b["upsell"])
    assert any("Loyal" in u["customer_name"] for u in b["upsell"])


@pytest.mark.asyncio
async def test_pipeline_insights_and_revenue(client: AsyncClient, setup):
    r = await client.get("/api/v1/sales-intelligence/pipeline-insights", headers=setup["h_admin"])
    b = r.json()
    assert "overview" in b and "funnel" in b and "velocity" in b and "lost_reasons" in b
    r = await client.get("/api/v1/sales-intelligence/revenue-prediction", headers=setup["h_admin"])
    b = r.json()
    assert "revenue_forecast" in b and "pipeline_forecast" in b
    assert b["pipeline_forecast"]["open_pipeline_value"] > 0


@pytest.mark.asyncio
async def test_deals_list_and_dashboard(client: AsyncClient, setup):
    r = await client.get("/api/v1/sales-intelligence/deals", headers=setup["h_admin"], params={"sort": "expected_value"})
    b = r.json()
    assert b["total"] == 2  # 2 open deals (strong + stalled)
    assert b["rows"][0]["lead_id"] == str(setup["strong"].id)
    r = await client.get("/api/v1/sales-intelligence/deals", headers=setup["h_admin"], params={"health": "strong"})
    assert all(d["health"] == "strong" for d in r.json()["rows"])
    r = await client.get("/api/v1/sales-intelligence/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["open_deals"] == 2 and d["weighted_pipeline_value"] > 0
    assert sum(d["by_health"].values()) == 2 and len(d["top_deals"]) >= 1


@pytest.mark.asyncio
async def test_report_and_export(client: AsyncClient, setup):
    r = await client.get("/api/v1/sales-intelligence/report", headers=setup["h_admin"])
    b = r.json()
    assert b["open_deals"] == 2 and sum(b["by_win_probability"].values()) == 2
    assert "competitor" in b
    r = await client.get("/api/v1/sales-intelligence/export", headers=setup["h_admin"])
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("lead_id,name,status,value,win_probability") and len(lines) == 3


@pytest.mark.asyncio
async def test_permissions(client: AsyncClient, setup):
    # employee (no downline, no deals) — dashboard is manager-gated
    r = await client.get("/api/v1/sales-intelligence/dashboard", headers=setup["h_emp"])
    assert r.status_code == 403
    r = await client.get("/api/v1/sales-intelligence/upsell", headers=setup["h_emp"])
    assert r.status_code == 403
    # non-existent deal
    r = await client.get(f"/api/v1/sales-intelligence/deals/{uuid.uuid4()}", headers=setup["h_admin"])
    assert r.status_code == 404

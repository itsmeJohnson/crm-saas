import json
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
from app.models.activity import Activity
from app.models.company import Company
from app.models.customer_order import CustomerOrder
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.contract import Contract
from app.models.audit_log import AuditLog
from app.services.compliance_service import classify
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
    org = await OrganizationRepository(db).create({"name": "Pred Org", "slug": "pred-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@pred.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@pred.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)

    # Leads: hot open (score+calls), stale open (never contacted), converted, lost
    hot = Lead(organization_id=org.id, first_name="Hot", last_name="Lead", title="t", status="Qualified",
               value=10000, score=80, priority="High", email="hot@x.com", company_name="HotCo",
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
               created_at=now - timedelta(days=5))
    stale = Lead(organization_id=org.id, last_name="Stale", title="t", status="New", value=500, score=10,
                 assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
                 created_at=now - timedelta(days=20))
    won = Lead(organization_id=org.id, last_name="Won", title="t", status="Converted", value=5000,
               converted_at=now - timedelta(days=2), assigned_user_id=admin.id, created_by=admin.id,
               stage_id=stage.id, created_at=now - timedelta(days=30))
    lost = Lead(organization_id=org.id, last_name="Lost", title="t", status="Lost", value=2000,
                assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
                created_at=now - timedelta(days=40))
    db.add_all([hot, stale, won, lost])
    await db.flush()
    db.add_all([
        Activity(organization_id=org.id, activity_type="Call", subject="c1", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Call", subject="c2", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Email", subject="e1", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
    ])

    # Customers: healthy (recent order+payment+active contract) vs churny (old, overdue invoice)
    good = Company(organization_id=org.id, name="GoodCo", created_by=admin.id, company_type="Customer")
    churny = Company(organization_id=org.id, name="ChurnyCo", created_by=admin.id, company_type="Customer")
    db.add_all([good, churny])
    await db.flush()
    db.add_all([
        CustomerOrder(organization_id=org.id, company_id=good.id, order_number="ORD-1", status="Fulfilled",
                      order_date=now - timedelta(days=10), total_amount=1000, created_by=admin.id),
        CustomerOrder(organization_id=org.id, company_id=churny.id, order_number="ORD-2", status="Fulfilled",
                      order_date=now - timedelta(days=250), total_amount=800, created_by=admin.id),
    ])
    inv_good = CustomerInvoice(organization_id=org.id, company_id=good.id, invoice_number="INV-1",
                               status="Paid", issue_date=now - timedelta(days=10),
                               due_date=now - timedelta(days=3), total_amount=1000, amount_paid=1000,
                               created_by=admin.id)
    inv_over = CustomerInvoice(organization_id=org.id, company_id=churny.id, invoice_number="INV-2",
                               status="Overdue", issue_date=now - timedelta(days=80),
                               due_date=now - timedelta(days=45), total_amount=800, amount_paid=0,
                               created_by=admin.id)
    inv_open = CustomerInvoice(organization_id=org.id, company_id=good.id, invoice_number="INV-3",
                               status="Sent", issue_date=now - timedelta(days=2),
                               due_date=now + timedelta(days=12), total_amount=500, amount_paid=0,
                               created_by=admin.id)
    db.add_all([inv_good, inv_over, inv_open])
    await db.flush()
    db.add(CustomerPayment(organization_id=org.id, company_id=good.id, invoice_id=inv_good.id,
                           amount=1000, paid_at=now - timedelta(days=5), created_by=admin.id))
    db.add(Contract(organization_id=org.id, company_id=good.id, contract_number="CT-1", title="Support",
                    status="Active", start_date=date.today() - timedelta(days=100),
                    end_date=date.today() + timedelta(days=60), created_by=admin.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "hot": hot, "stale": stale,
            "good": good, "churny": churny, "inv_over": inv_over, "inv_open": inv_open, "inv_good": inv_good,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_documents_all_datasets(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/catalog", headers=setup["h_admin"])
    body = r.json()
    assert body["method"] == "heuristic_v1" and body["ai_ready"] is True
    keys = {d["key"] for d in body["datasets"]}
    assert keys == {"lead_conversion", "sales_pipeline", "customer_churn", "customer_clv",
                    "customer_risk", "invoice_collection", "employee_performance", "recommendations"}
    lead_ds = next(d for d in body["datasets"] if d["key"] == "lead_conversion")
    assert "score" in lead_ds["features"] and "target" in lead_ds


@pytest.mark.asyncio
async def test_lead_conversion_dataset_labels_and_features(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/lead_conversion", headers=setup["h_admin"])
    rows = {x["lead_id"]: x for x in r.json()["rows"]}
    assert rows[str(setup["hot"].id)]["converted"] is None  # open
    assert rows[str(setup["hot"].id)]["calls"] == 2 and rows[str(setup["hot"].id)]["emails"] == 1
    won = next(x for x in rows.values() if x["status"] == "Converted")
    lost = next(x for x in rows.values() if x["status"] == "Lost")
    assert won["converted"] == 1 and lost["converted"] == 0
    bad = await client.get("/api/v1/predictive/datasets/nope", headers=setup["h_admin"])
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_sales_pipeline_expected_value(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/sales_pipeline", headers=setup["h_admin"])
    rows = {x["lead_id"]: x for x in r.json()["rows"]}
    hot = rows[str(setup["hot"].id)]
    assert hot["outcome"] == "open" and hot["conversion_probability"] > 50
    assert hot["expected_value"] == round(10000 * hot["conversion_probability"] / 100, 2)
    won = next(x for x in rows.values() if x["outcome"] == "won")
    assert won["won_value"] == 5000 and won["conversion_probability"] is None


@pytest.mark.asyncio
async def test_predict_lead_with_factors(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/predictive/predict/lead/{setup['hot'].id}", headers=setup["h_admin"])
    body = r.json()
    assert body["method"] == "heuristic_v1" and body["ai_ready"] is True
    assert body["conversion_probability"] > 50
    assert any("call" in f["factor"] for f in body["factors"])
    # stale never-contacted lead scores much lower
    r2 = await client.get(f"/api/v1/predictive/predict/lead/{setup['stale'].id}", headers=setup["h_admin"])
    assert r2.json()["conversion_probability"] < body["conversion_probability"]
    import uuid as _uuid
    assert (await client.get(f"/api/v1/predictive/predict/lead/{_uuid.uuid4()}",
                             headers=setup["h_admin"])).status_code == 404


@pytest.mark.asyncio
async def test_churn_dataset_and_prediction(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/customer_churn", headers=setup["h_admin"])
    rows = {x["customer_id"]: x for x in r.json()["rows"]}
    good, churny = rows[str(setup["good"].id)], rows[str(setup["churny"].id)]
    assert good["churned"] == 0 and good["active_contracts"] == 1
    assert churny["churn_risk"] > good["churn_risk"]
    r = await client.get(f"/api/v1/predictive/predict/churn/{setup['churny'].id}", headers=setup["h_admin"])
    body = r.json()
    assert body["churn_risk"] >= 60 and body["band"] == "high"
    assert any("no active contract" in f["factor"] for f in body["factors"])


@pytest.mark.asyncio
async def test_clv_prediction(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/predictive/predict/clv/{setup['good'].id}", headers=setup["h_admin"])
    body = r.json()
    assert body["historic_value"] == 1000
    assert body["predicted_clv"] > body["historic_value"]
    assert body["horizon_months"] == 12 and 0.2 <= body["retention_factor"] <= 1.0
    r = await client.get(f"/api/v1/predictive/predict/clv/{setup['good'].id}",
                         headers=setup["h_admin"], params={"horizon_months": 24})
    assert r.json()["predicted_clv"] > body["predicted_clv"]


@pytest.mark.asyncio
async def test_risk_score(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/customer_risk", headers=setup["h_admin"])
    rows = {x["customer_id"]: x for x in r.json()["rows"]}
    assert rows[str(setup["churny"].id)]["risk_score"] > rows[str(setup["good"].id)]["risk_score"]
    r = await client.get(f"/api/v1/predictive/predict/risk/{setup['churny'].id}", headers=setup["h_admin"])
    assert r.json()["risk_band"] in ("medium", "high")


@pytest.mark.asyncio
async def test_collection_probability(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/invoice_collection", headers=setup["h_admin"])
    rows = {x["invoice_id"]: x for x in r.json()["rows"]}
    overdue, current = rows[str(setup["inv_over"].id)], rows[str(setup["inv_open"].id)]
    paid = rows[str(setup["inv_good"].id)]
    assert overdue["aging_bucket"] == "31-60" and current["aging_bucket"] == "current"
    assert overdue["collection_probability"] < current["collection_probability"]
    assert paid["collection_probability"] is None and paid["paid_on_time"] == 1
    r = await client.get(f"/api/v1/predictive/predict/collection/{setup['inv_over'].id}", headers=setup["h_admin"])
    assert r.json()["collection_probability"] < 70


@pytest.mark.asyncio
async def test_employee_performance_dataset_and_prediction(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/datasets/employee_performance", headers=setup["h_admin"])
    rows = {x["user_id"]: x for x in r.json()["rows"]}
    admin_row = rows[str(setup["admin"].id)]
    assert admin_row["activities_30d"] >= 3 and admin_row["score_30d"] > 0
    assert "predicted_next_30d_score" in admin_row and "trend_pct" in admin_row
    r = await client.get(f"/api/v1/predictive/predict/employee/{setup['admin'].id}", headers=setup["h_admin"])
    assert r.json()["method"] == "heuristic_v1" and r.json()["predicted_next_30d_score"] >= 0


@pytest.mark.asyncio
async def test_recommendations(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/recommendations", headers=setup["h_admin"])
    recs = r.json()
    actions = {x["action"] for x in recs}
    assert "Make first contact" in actions          # stale never-contacted lead
    assert "Collect overdue balance" in actions      # churny overdue invoice
    assert "Start renewal conversation" in actions   # good contract expiring in 60d
    r = await client.get("/api/v1/predictive/recommendations", headers=setup["h_admin"],
                         params={"scope": "customers"})
    assert all(x["entity_type"] == "customer" for x in r.json())


@pytest.mark.asyncio
async def test_training_export_csv_json_and_audit(client: AsyncClient, setup, db: AsyncSession):
    r = await client.get("/api/v1/predictive/datasets/lead_conversion/export",
                         headers=setup["h_admin"], params={"format": "csv"})
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert "converted" in lines[0] and len(lines) == 5  # header + 4 leads

    r = await client.get("/api/v1/predictive/datasets/customer_churn/export",
                         headers=setup["h_admin"], params={"format": "json"})
    body = json.loads(r.content)
    assert body["dataset"] == "customer_churn" and len(body["rows"]) == 2

    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "TRAINING_DATASET_EXPORTED"))).scalars().all()
    assert len(audits) == 2
    # compliance classifier files these under Data Exports
    assert classify("TRAINING_DATASET_EXPORTED") == "export"


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, setup):
    r = await client.get("/api/v1/predictive/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["open_leads"] == 2 and d["customers_tracked"] == 2
    assert d["expected_pipeline_value"] > 0
    assert d["customers_at_high_churn_risk"] >= 1
    assert len(d["hot_leads"]) >= 1 and d["hot_leads"][0]["lead_id"] == str(setup["hot"].id)
    assert d["recommendations"] > 0 and len(d["top_recommendations"]) > 0


@pytest.mark.asyncio
async def test_employee_forbidden(client: AsyncClient, setup):
    for path in ("/api/v1/predictive/dashboard", "/api/v1/predictive/datasets/lead_conversion",
                 "/api/v1/predictive/recommendations"):
        assert (await client.get(path, headers=setup["h_emp"])).status_code == 403

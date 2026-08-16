import uuid
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
from app.models.task import Task
from app.models.campaign import Campaign
from app.models.audit_log import AuditLog
from app.services.prediction_engine_service import (
    confidence_score, MODEL_REGISTRY, ENGINE_VERSION,
)
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


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "PE Org", "slug": "pe-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@pe.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@pe.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = _now()

    hot = Lead(organization_id=org.id, first_name="Hot", last_name="Lead", title="t", status="Qualified",
               value=10000, score=80, priority="High", email="hot@x.com", company_name="HotCo",
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
               created_at=now - timedelta(days=5))
    won = Lead(organization_id=org.id, last_name="Won", title="t", status="Converted", value=5000,
               score=75, converted_at=now - timedelta(days=2), assigned_user_id=admin.id,
               created_by=admin.id, stage_id=stage.id, created_at=now - timedelta(days=30))
    lost = Lead(organization_id=org.id, last_name="Lost", title="t", status="Lost", value=2000,
                score=10, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
                created_at=now - timedelta(days=40))
    db.add_all([hot, won, lost])
    await db.flush()
    db.add_all([
        Activity(organization_id=org.id, activity_type="Call", subject="c1", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Call", subject="c2", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
    ])

    good = Company(organization_id=org.id, name="GoodCo", created_by=admin.id)
    db.add(good)
    await db.flush()
    db.add(CustomerOrder(organization_id=org.id, company_id=good.id, order_number="ORD-1",
                         status="Fulfilled", order_date=now - timedelta(days=20),
                         total_amount=1000, created_by=admin.id))
    inv_good = CustomerInvoice(organization_id=org.id, company_id=good.id, invoice_number="INV-1",
                               status="Paid", issue_date=now - timedelta(days=10),
                               due_date=now - timedelta(days=3), total_amount=1000, amount_paid=1000,
                               created_by=admin.id)
    inv_open = CustomerInvoice(organization_id=org.id, company_id=good.id, invoice_number="INV-2",
                               status="Sent", issue_date=now - timedelta(days=2),
                               due_date=now + timedelta(days=12), total_amount=500, amount_paid=0,
                               created_by=admin.id)
    db.add_all([inv_good, inv_open])
    await db.flush()
    db.add(CustomerPayment(organization_id=org.id, company_id=good.id, invoice_id=inv_good.id,
                           amount=1000, paid_at=now - timedelta(days=5), created_by=admin.id))
    db.add(Contract(organization_id=org.id, company_id=good.id, contract_number="CT-1", title="Support",
                    status="Active", start_date=date.today() - timedelta(days=100),
                    end_date=date.today() + timedelta(days=60), created_by=admin.id))

    # Tasks: overdue-open (high delay risk), due-soon in-progress, historical done-late & done-on-time
    overdue = Task(organization_id=org.id, title="Overdue task", status="Todo", priority="High",
                   due_date=now - timedelta(days=2), assigned_user_id=emp.id, created_by=admin.id)
    soon = Task(organization_id=org.id, title="Due soon", status="InProgress", priority="Medium",
                due_date=now + timedelta(hours=10), assigned_user_id=emp.id, created_by=admin.id)
    done_late = Task(organization_id=org.id, title="Was late", status="Done", priority="Low",
                     due_date=now - timedelta(days=10), completed_at=now - timedelta(days=8),
                     assigned_user_id=emp.id, created_by=admin.id)
    done_ok = Task(organization_id=org.id, title="On time", status="Done", priority="Low",
                   due_date=now - timedelta(days=6), completed_at=now - timedelta(days=7),
                   assigned_user_id=emp.id, created_by=admin.id)
    db.add_all([overdue, soon, done_late, done_ok])

    # Campaigns: one completed (builds benchmarks) + one draft (to predict)
    done_campaign = Campaign(organization_id=org.id, name="Past Email Blast", channel="Email",
                             status="completed", total_recipients=1000, sent_count=1000,
                             delivered_count=970, opened_count=300, clicked_count=45,
                             converted_count=20, cost_per_message=0.5, revenue=40000,
                             created_by=admin.id)
    draft_campaign = Campaign(organization_id=org.id, name="Upcoming Promo", channel="Email",
                              status="draft", total_recipients=500, cost_per_message=0.5,
                              created_by=admin.id)
    db.add_all([done_campaign, draft_campaign])
    await db.commit()

    return {"org": org, "admin": admin, "emp": emp, "hot": hot, "won": won, "lost": lost,
            "good": good, "inv_open": inv_open,
            "overdue": overdue, "soon": soon, "draft_campaign": draft_campaign,
            "done_campaign": done_campaign,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- confidence (pure) ----------
def test_confidence_score_math():
    strong = confidence_score(sample_size=40, completeness=1.0, signal_strength=1.0, sample_target=20)
    assert strong["confidence"] == 100.0 and strong["confidence_band"] == "high"
    weak = confidence_score(sample_size=0, completeness=0.0, signal_strength=0.0)
    assert weak["confidence"] == 0.0 and weak["confidence_band"] == "low"
    mid = confidence_score(sample_size=10, completeness=0.5, signal_strength=0.5, sample_target=20)
    assert 30 <= mid["confidence"] <= 60


# ---------- model registry / version ----------
@pytest.mark.asyncio
async def test_model_registry(client: AsyncClient, setup):
    r = await client.get("/api/v1/prediction-engine/models", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["engine_version"] == ENGINE_VERSION
    keys = {m["key"] for m in body["models"]}
    assert {"lead_conversion", "sales_pipeline", "revenue", "customer_churn", "invoice_collection",
            "task_delay", "employee_performance", "campaign_response"} <= keys
    for m in body["models"]:
        assert m["version"] and m["type"] in ("classification", "regression", "timeseries")
    assert (await client.get("/api/v1/prediction-engine/models", headers=setup["h_emp"])).status_code == 403


# ---------- confidence + version on composed predictions ----------
@pytest.mark.asyncio
async def test_lead_prediction_has_confidence_and_version(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/prediction-engine/predict/lead/{setup['hot'].id}",
                         headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "lead_conversion"
    assert body["model_version"] == MODEL_REGISTRY["lead_conversion"]["version"]
    assert body["engine_version"] == ENGINE_VERSION
    assert 0 <= body["confidence"] <= 100 and body["confidence_band"] in ("low", "medium", "high")
    assert body["conversion_probability"] > 50
    assert "confidence_factors" in body


# ---------- NEW: task delay prediction ----------
@pytest.mark.asyncio
async def test_task_delay_prediction(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/prediction-engine/predict/task/{setup['overdue'].id}",
                         headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "task_delay" and body["predicted_late"] is True
    assert body["delay_risk"] >= 50
    assert any("overdue" in f["factor"] for f in body["factors"])
    # assignee has an on-time history (1 late / 1 on-time = 50%)
    assert body["assignee_on_time_rate"] == 50.0

    lst = (await client.get("/api/v1/prediction-engine/predict/tasks", headers=setup["h_admin"])).json()
    assert lst["open_tasks"] == 2 and lst["at_risk"] >= 1
    assert lst["predictions"][0]["delay_risk"] >= lst["predictions"][-1]["delay_risk"]


# ---------- NEW: campaign prediction ----------
@pytest.mark.asyncio
async def test_campaign_prediction(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/prediction-engine/predict/campaign/{setup['draft_campaign'].id}",
                         headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "campaign_response" and body["audience_size"] == 500
    pred = body["predicted"]
    # historical Email benchmark: delivery 970/1000, conversion 20/1000 → 500*0.02 = 10
    assert pred["delivered"] == round(500 * 0.97)
    assert pred["converted"] == 10
    assert pred["roi_pct"] is not None
    assert body["benchmark_source"] == "historical"

    lst = (await client.get("/api/v1/prediction-engine/predict/campaigns",
                            headers=setup["h_admin"])).json()
    assert lst["count"] == 1  # only the draft is pending; completed excluded
    assert "Email" in lst["channel_benchmarks"]


# ---------- sales + revenue ----------
@pytest.mark.asyncio
async def test_sales_and_revenue_prediction(client: AsyncClient, setup):
    s = (await client.get("/api/v1/prediction-engine/predict/sales", headers=setup["h_admin"])).json()
    assert s["model"] == "sales_pipeline"
    assert s["open_deals"] == 1 and s["open_pipeline_value"] == 10000
    assert s["win_rate"] == 50.0  # 1 won / (1 won + 1 lost)
    assert "confidence" in s

    rev = (await client.get("/api/v1/prediction-engine/predict/revenue?periods=3",
                            headers=setup["h_admin"])).json()
    assert rev["model"] == "revenue" and rev["model_type"] == "timeseries"
    assert len(rev["forecast"]) == 3 and "confidence" in rev


# ---------- forecast accuracy ----------
@pytest.mark.asyncio
async def test_forecast_accuracy(client: AsyncClient, setup):
    r = await client.get("/api/v1/prediction-engine/accuracy", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["engine_version"] == ENGINE_VERSION
    models = {c["model"] for c in body["classification"]}
    assert "lead_conversion" in models and "customer_churn" in models
    lead_acc = next(c for c in body["classification"] if c["model"] == "lead_conversion")
    # won(prob≥? actually converted excluded from open) — closed leads: won label 1, lost label 0
    assert lead_acc["samples"] == 2
    assert lead_acc["accuracy"] is not None and lead_acc["brier"] is not None
    assert [r["model"] for r in body["regression"]] == ["revenue", "sales_pipeline"]


# ---------- dashboard + report + export + permissions ----------
@pytest.mark.asyncio
async def test_dashboard_report_export(client: AsyncClient, setup, db: AsyncSession):
    dash = (await client.get("/api/v1/prediction-engine/dashboard", headers=setup["h_admin"])).json()
    assert dash["engine_version"] == ENGINE_VERSION and dash["models_active"] == len(MODEL_REGISTRY)
    assert dash["sales"]["open_deals"] == 1
    assert dash["tasks"]["open"] == 2 and dash["tasks"]["at_risk"] >= 1

    rep = (await client.get("/api/v1/prediction-engine/report", headers=setup["h_admin"])).json()
    assert rep["summary"]["open_pipeline_value"] == 10000
    assert "accuracy" in rep and len(rep["models"]) == len(MODEL_REGISTRY)

    assert (await client.get("/api/v1/prediction-engine/export",
                             headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/prediction-engine/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "summary" in r.text
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "PREDICTION_REPORT_EXPORTED"))).scalars().all()
    assert len(audits) == 1

    # all prediction endpoints are manager-gated
    assert (await client.get("/api/v1/prediction-engine/dashboard",
                             headers=setup["h_emp"])).status_code == 403

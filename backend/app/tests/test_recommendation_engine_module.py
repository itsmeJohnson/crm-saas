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
from app.models.recommendation import RecommendationFeedback
from app.models.audit_log import AuditLog
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


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Rec Org", "slug": "rec-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@rec.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@rec.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = _now()

    # hot open lead (phone + calls → NBA push, callable), stale open lead (idle → follow-up),
    # brand-new never-contacted lead (first touch)
    hot = Lead(organization_id=org.id, first_name="Hot", last_name="Lead", title="t", status="Qualified",
               value=20000, score=85, priority="High", email="hot@x.com", phone="9990001111",
               company_name="HotCo", assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id,
               created_at=now - timedelta(days=5))
    stale = Lead(organization_id=org.id, first_name="Stale", last_name="Lead", title="t", status="Contacted",
                 value=4000, score=60, assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id,
                 created_at=now - timedelta(days=25))
    fresh = Lead(organization_id=org.id, first_name="Fresh", last_name="Lead", title="t", status="New",
                 value=1000, score=20, assigned_user_id=emp.id, created_by=admin.id, stage_id=stage.id,
                 created_at=now - timedelta(days=3))
    db.add_all([hot, stale, fresh])
    await db.flush()
    # hot lead: recent calls; stale lead: an old activity 20d ago
    db.add_all([
        Activity(organization_id=org.id, activity_type="Call", subject="c1", lead_id=hot.id,
                 assigned_user_id=emp.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Call", subject="c2", lead_id=hot.id,
                 assigned_user_id=emp.id, created_by=admin.id),
    ])
    await db.flush()
    old_act = Activity(organization_id=org.id, activity_type="Email", subject="old", lead_id=stale.id,
                       assigned_user_id=emp.id, created_by=admin.id)
    db.add(old_act)
    await db.flush()
    old_act.created_at = now - timedelta(days=20)

    # a customer with an overdue invoice → follow-up (chase payment) + product upsell base
    cust = Company(organization_id=org.id, name="PayLate Inc", created_by=admin.id)
    db.add(cust)
    await db.flush()
    db.add(CustomerOrder(organization_id=org.id, company_id=cust.id, order_number="ORD-1",
                         status="Fulfilled", order_date=now - timedelta(days=40),
                         total_amount=5000, created_by=admin.id))
    db.add(CustomerInvoice(organization_id=org.id, company_id=cust.id, invoice_number="INV-1",
                           status="Overdue", issue_date=now - timedelta(days=60),
                           due_date=now - timedelta(days=30), total_amount=5000, amount_paid=0,
                           created_by=admin.id))
    await db.commit()

    return {"org": org, "admin": admin, "emp": emp, "hot": hot, "stale": stale, "fresh": fresh,
            "cust": cust,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- per-type generators ----------
@pytest.mark.asyncio
async def test_next_best_actions(client: AsyncClient, setup):
    r = await client.get("/api/v1/recommendations/next-best-actions", headers=setup["h_admin"])
    assert r.status_code == 200
    recs = r.json()
    assert all(x["rec_type"] == "next_best_action" for x in recs)
    hot = next(x for x in recs if x["target_id"] == str(setup["hot"].id))
    assert hot["payload"]["action"] in ("Push to close", "Follow up", "Nurture")
    assert hot["rec_key"] == f"next_best_action:lead:{setup['hot'].id}"


@pytest.mark.asyncio
async def test_follow_ups_and_call_times(client: AsyncClient, setup):
    fu = (await client.get("/api/v1/recommendations/follow-ups", headers=setup["h_admin"])).json()
    keys = {x["rec_key"] for x in fu}
    assert f"follow_up:lead:{setup['stale'].id}" in keys  # idle 20d
    assert f"follow_up:customer:{setup['cust'].id}" in keys  # overdue invoice

    ct = (await client.get("/api/v1/recommendations/call-times", headers=setup["h_admin"])).json()
    assert any(x["rec_key"] == "call_time:org:peak" for x in ct)  # heatmap peak exists
    assert any(x["target_id"] == str(setup["hot"].id) for x in ct)  # hot callable lead


@pytest.mark.asyncio
async def test_recommended_agent(client: AsyncClient, setup):
    r = await client.get("/api/v1/recommendations/agents", headers=setup["h_admin"])
    assert r.status_code == 200
    agents = r.json()
    assert all(a["rec_type"] == "agent" for a in agents)
    assert any(a["target_id"] == str(setup["emp"].id) for a in agents)
    # employees cannot request agent recommendations (manager-gated)
    assert (await client.get("/api/v1/recommendations/agents", headers=setup["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_products_manager_gated(client: AsyncClient, setup):
    r = await client.get("/api/v1/recommendations/products", headers=setup["h_admin"])
    assert r.status_code == 200  # PayLate Inc has an order → upsell/cross candidate
    assert (await client.get("/api/v1/recommendations/products", headers=setup["h_emp"])).status_code == 403


# ---------- unified feed + persistence ----------
@pytest.mark.asyncio
async def test_feed_persists_and_dedups(client: AsyncClient, setup, db: AsyncSession):
    r = await client.get("/api/v1/recommendations/feed", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert "next_best_action" in body["types_present"]
    # every surfaced rec has an id + pending action + personalized score
    for rec in body["recommendations"]:
        assert rec["id"] and rec["action"] == "pending"
        assert rec["personalized_score"] >= 0
    # persisted rows exist
    rows = (await db.execute(select(RecommendationFeedback).filter(
        RecommendationFeedback.organization_id == setup["org"].id))).scalars().all()
    assert len(rows) == body["count"]
    # regenerating does not duplicate rows (idempotent per user+key)
    await client.get("/api/v1/recommendations/feed", headers=setup["h_admin"])
    rows2 = (await db.execute(select(RecommendationFeedback).filter(
        RecommendationFeedback.organization_id == setup["org"].id))).scalars().all()
    assert len(rows2) == len(rows)


# ---------- feedback loop: dismiss suppresses; accept up-weights ----------
@pytest.mark.asyncio
async def test_feedback_loop(client: AsyncClient, setup, db: AsyncSession):
    feed = (await client.get("/api/v1/recommendations/feed", headers=setup["h_admin"])).json()
    target = feed["recommendations"][0]

    # dismiss it → next feed must not contain it
    r = await client.post("/api/v1/recommendations/feedback", headers=setup["h_admin"],
                          json={"feedback_id": target["id"], "action": "dismissed"})
    assert r.status_code == 200 and r.json()["action"] == "dismissed"
    feed2 = (await client.get("/api/v1/recommendations/feed", headers=setup["h_admin"])).json()
    assert all(rec["rec_key"] != target["rec_key"] for rec in feed2["recommendations"])

    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "RECOMMENDATION_FEEDBACK"))).scalars().all()
    assert len(audits) == 1

    # accepting several NBA recs lifts that type's personalization multiplier > 1.0
    for rec in [r for r in feed2["recommendations"] if r["rec_type"] == "next_best_action"][:2]:
        await client.post("/api/v1/recommendations/feedback", headers=setup["h_admin"],
                          json={"feedback_id": rec["id"], "action": "accepted"})
    p = (await client.get("/api/v1/recommendations/personalized", headers=setup["h_admin"])).json()
    assert p["personalization"]["next_best_action"] > 1.0
    assert "next_best_action" in p["explanation"]["boosted_types"]


@pytest.mark.asyncio
async def test_feedback_by_rec_key_creates_row(client: AsyncClient, setup, db: AsyncSession):
    # snooze a rec that isn't persisted yet, addressing it by rec_key
    r = await client.post("/api/v1/recommendations/feedback", headers=setup["h_emp"], json={
        "rec_key": "knowledge:custom-1", "rec_type": "knowledge", "title": "Read pricing FAQ",
        "action": "snoozed", "snooze_hours": 48})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "snoozed" and body["snooze_until"]
    row = (await db.execute(select(RecommendationFeedback).filter(
        RecommendationFeedback.rec_key == "knowledge:custom-1"))).scalars().first()
    assert row is not None and row.user_id == setup["emp"].id
    # missing rec_type/title on a brand-new key → 400
    bad = await client.post("/api/v1/recommendations/feedback", headers=setup["h_emp"],
                            json={"rec_key": "unknown:x", "action": "accepted"})
    assert bad.status_code == 400


# ---------- analytics + report + export + permissions ----------
@pytest.mark.asyncio
async def test_analytics_report_export(client: AsyncClient, setup, db: AsyncSession):
    feed = (await client.get("/api/v1/recommendations/feed", headers=setup["h_admin"])).json()
    recs = feed["recommendations"]
    await client.post("/api/v1/recommendations/feedback", headers=setup["h_admin"],
                      json={"feedback_id": recs[0]["id"], "action": "accepted"})
    await client.post("/api/v1/recommendations/feedback", headers=setup["h_admin"],
                      json={"feedback_id": recs[1]["id"], "action": "dismissed"})

    an = (await client.get("/api/v1/recommendations/analytics", headers=setup["h_admin"])).json()
    assert an["totals"]["shown"] >= 2
    assert an["totals"]["accepted"] == 1 and an["totals"]["dismissed"] == 1
    assert an["overall_acceptance_rate"] == 50.0
    assert any(t["rec_type"] and t["acceptance_rate"] is not None for t in an["by_type"])

    rep = (await client.get("/api/v1/recommendations/report", headers=setup["h_admin"])).json()
    assert "summary" in rep and "analytics" in rep

    assert (await client.get("/api/v1/recommendations/analytics",
                             headers=setup["h_emp"])).status_code == 403
    assert (await client.get("/api/v1/recommendations/export",
                             headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/recommendations/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "rec_type" in r.text
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "RECOMMENDATIONS_EXPORTED"))).scalars().all()
    assert len(audits) == 1


# ---------- employees get a personalized feed too (downline-scoped) ----------
@pytest.mark.asyncio
async def test_employee_feed_scoped(client: AsyncClient, setup):
    r = await client.get("/api/v1/recommendations/feed", headers=setup["h_emp"])
    assert r.status_code == 200
    body = r.json()
    # employee owns the leads → gets NBA/follow-up recs, but no manager-only types
    assert body["count"] > 0
    assert "product" not in body["types_present"]
    assert "workflow" not in body["types_present"]
    dash = (await client.get("/api/v1/recommendations/dashboard", headers=setup["h_emp"])).json()
    assert "top_recommendations" in dash and "my_pending" in dash

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
    org = await OrganizationRepository(db).create({"name": "Sales Org", "slug": "sales-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@sa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@sa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    from app.models.pipeline import Pipeline
    pipeline_stmt = select(Pipeline).filter(Pipeline.organization_id == org.id, Pipeline.is_default == True)
    pipeline = (await db.execute(pipeline_stmt)).scalars().first()

    existing = list((await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_deleted == False))).scalars().all())
    stages = {s.name: s for s in existing}
    next_pos = (max([s.order_position for s in existing], default=0)) + 1
    for nm in ["New", "Contacted", "Converted"]:
        if nm not in stages:
            st = PipelineStage(organization_id=org.id, pipeline_id=pipeline.id, name=nm, order_position=next_pos, is_system_default=False)
            db.add(st); await db.flush()
            stages[nm] = st
            next_pos += 1
    await db.commit()
    now = datetime.now(timezone.utc)

    def mk(status, value, source, **kw):
        kw.setdefault("stage_id", stages["New"].id)
        return Lead(organization_id=org.id, last_name="L", title="t", status=status, value=value, source=source,
                    created_by=admin.id, assigned_user_id=admin.id, **kw)

    # 2 won (converted 5 & 15 days) from Website+Referral, 2 lost (reasons), 2 open
    db.add(mk("Converted", 1000, "Website", converted_at=now - timedelta(days=1), created_at=now - timedelta(days=6), stage_id=stages["Converted"].id))
    db.add(mk("Converted", 3000, "Referral", converted_at=now - timedelta(days=1), created_at=now - timedelta(days=16), stage_id=stages["Converted"].id))
    db.add(mk("Lost", 500, "Website", lost_reason="Price", created_at=now - timedelta(days=10)))
    db.add(mk("Lost", 800, "Website", lost_reason="Timing", created_at=now - timedelta(days=8)))
    db.add(mk("New", 2000, "Website", created_at=now - timedelta(days=3)))
    db.add(mk("Contacted", 4000, "Referral", created_at=now - timedelta(days=2), stage_id=stages["Contacted"].id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stages": stages,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_overview_metrics_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    assert (await client.get("/api/v1/sales-analytics/overview", headers=d["h_emp"])).status_code == 403
    ov = (await client.get("/api/v1/sales-analytics/overview", headers=d["h_admin"])).json()
    assert ov["total_leads"] == 6 and ov["won"] == 2 and ov["lost"] == 2 and ov["open"] == 2
    assert ov["revenue"] == 4000.0 and ov["avg_deal_size"] == 2000.0
    # win rate = won/(won+lost) = 2/4 = 50; conversion = won/total = 2/6 = 33.3
    assert ov["win_rate"] == 50.0 and ov["conversion_rate"] == 33.3
    # avg cycle: (5 + 15)/2 = 10 days
    assert ov["avg_sales_cycle_days"] == 10.0
    # velocity = (open 2 × 0.5 × 2000) / 10 = 200
    assert ov["sales_velocity"] == 200.0


@pytest.mark.asyncio
async def test_funnel_conversion_revenue_and_sources(client: AsyncClient, setup: dict):
    d = setup
    fn = (await client.get("/api/v1/sales-analytics/funnel", headers=d["h_admin"])).json()
    stages = {s["stage"]: s for s in fn["sales_funnel"]}
    assert stages["Converted"]["count"] == 2 and stages["Contacted"]["count"] == 1
    assert any(s["status"] == "New" for s in fn["lead_funnel"])
    conv = (await client.get("/api/v1/sales-analytics/conversion", headers=d["h_admin"])).json()
    web = next(r for r in conv["by_source"] if r["source"] == "Website")
    assert web["leads"] == 4 and web["won"] == 1  # 1 of 4 website leads converted
    rev = (await client.get("/api/v1/sales-analytics/revenue", headers=d["h_admin"])).json()
    assert rev["revenue"] == 4000.0 and rev["won_deals"] == 2
    roi = (await client.get("/api/v1/sales-analytics/sources", headers=d["h_admin"])).json()
    ref = next(r for r in roi["sources"] if r["source"] == "Referral")
    assert ref["revenue"] == 3000.0 and ref["avg_deal_size"] == 3000.0


@pytest.mark.asyncio
async def test_lost_reasons_velocity_and_forecast(client: AsyncClient, setup: dict):
    d = setup
    lost = (await client.get("/api/v1/sales-analytics/lost-reasons", headers=d["h_admin"])).json()
    assert lost["total_lost"] == 2
    reasons = {r["reason"]: r for r in lost["by_reason"]}
    assert "Price" in reasons and "Timing" in reasons and reasons["Price"]["share_pct"] == 50.0
    vel = (await client.get("/api/v1/sales-analytics/velocity", headers=d["h_admin"])).json()
    assert vel["win_rate"] == 50.0 and vel["avg_sales_cycle_days"] == 10.0 and vel["median_cycle_days"] == 10.0
    assert vel["min_cycle_days"] == 5.0 and vel["max_cycle_days"] == 15.0 and vel["sales_velocity"] == 200.0
    fc = (await client.get("/api/v1/sales-analytics/forecast", headers=d["h_admin"])).json()
    # open pipeline value = 2000 + 4000 = 6000; weighted = 6000 * 33.3% ≈ 1998; projected = 4000 + weighted
    assert fc["open_pipeline_value"] == 6000.0 and fc["realised_revenue"] == 4000.0
    assert fc["projected_total"] == round(4000.0 + fc["weighted_pipeline"], 2)


@pytest.mark.asyncio
async def test_trend_heatmap_dashboard_and_export(client: AsyncClient, setup: dict):
    d = setup
    tr = (await client.get("/api/v1/sales-analytics/trend", params={"granularity": "monthly"}, headers=d["h_admin"])).json()
    assert tr["granularity"] == "monthly" and sum(b["leads"] for b in tr["series"]) == 6
    assert (await client.get("/api/v1/sales-analytics/trend", params={"granularity": "yearly"}, headers=d["h_admin"])).status_code == 400
    hm = (await client.get("/api/v1/sales-analytics/heatmap", headers=d["h_admin"])).json()
    assert len(hm["grid"]) == 7 and len(hm["grid"][0]) == 24 and sum(sum(r) for r in hm["grid"]) == 6
    dash = (await client.get("/api/v1/sales-analytics/dashboard", headers=d["h_admin"])).json()
    assert dash["win_rate"] == 50.0 and dash["revenue"] == 4000.0
    exp = await client.get("/api/v1/sales-analytics/export", headers=d["h_admin"])
    assert exp.status_code == 200 and "Sales analytics" in exp.text and "Lost reason" in exp.text

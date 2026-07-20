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
    org = await OrganizationRepository(db).create({"name": "LI Org", "slug": "li-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@li.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@li.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    hot = Lead(organization_id=org.id, first_name="Hot", last_name="Prospect", title="t", status="Qualified",
               value=50000, score=0, priority="High", email="hot@x.com", phone="+911111100000",
               company_name="HotCorp", city="Mumbai", source="Referral",
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
               created_at=now - timedelta(days=3))
    cold = Lead(organization_id=org.id, last_name="Coldman", title="t", status="New", value=0, score=0,
                assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id,
                created_at=now - timedelta(days=90))
    dup = Lead(organization_id=org.id, first_name="Hotter", last_name="Prospect", title="t", status="New",
               value=1000, email="hot@x.com", company_name="HotCorp",
               assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add_all([hot, cold, dup])
    await db.flush()
    db.add_all([
        Activity(organization_id=org.id, activity_type="Call", subject="c1", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Call", subject="c2", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
        Activity(organization_id=org.id, activity_type="Email", subject="e1", lead_id=hot.id,
                 assigned_user_id=admin.id, created_by=admin.id),
    ])
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "hot": hot, "cold": cold, "dup": dup,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_lead_intelligence_full_bundle(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/lead-intelligence/leads/{setup['hot'].id}", headers=setup["h_admin"])
    assert r.status_code == 200, r.text
    b = r.json()
    # scoring + grade
    assert b["score"] > 50 and b["score_grade"] in ("A", "B")
    # hot detection: high probability + recent activity
    assert b["temperature"] == "hot" and b["conversion_probability"] > 55
    assert b["recommended_priority"] == "High"
    # opportunity/risk/quality
    assert b["opportunity_score"] > 0 and b["risk_score"] >= 0 and b["quality_grade"] in ("A", "B", "C", "D")
    # completeness — hot lead has most fields
    assert b["completeness"]["pct"] >= 70
    # conversion factors + next best action + insights
    assert any("call" in f["factor"] for f in b["conversion_factors"])
    assert b["next_best_action"]["action"] and b["insights"]
    # duplicate suggestions: shares email + company with the dup lead
    dups = b["duplicate_suggestions"]
    assert any(d["lead_id"] == str(setup["dup"].id) and "same email" in d["match_on"] for d in dups)


@pytest.mark.asyncio
async def test_cold_lead_detection(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/lead-intelligence/leads/{setup['cold'].id}", headers=setup["h_admin"])
    b = r.json()
    assert b["temperature"] == "cold"
    assert b["recommended_priority"] == "Low"
    # incomplete → enrichment suggestions for the missing fields
    fields = {e["field"] for e in b["enrichment_suggestions"]}
    assert "email" in fields and "phone" in fields
    assert b["completeness"]["pct"] < 50
    # never contacted, aged → risk reasons
    assert b["risk_score"] > 0 and b["risk_reasons"]


@pytest.mark.asyncio
async def test_duplicates_endpoint(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/lead-intelligence/leads/{setup['hot'].id}/duplicates", headers=setup["h_admin"])
    dups = r.json()
    assert len(dups) >= 1
    top = next(d for d in dups if d["lead_id"] == str(setup["dup"].id))
    assert top["confidence"] == "high" and "same email" in top["match_on"]


@pytest.mark.asyncio
async def test_summary_via_gateway(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/lead-intelligence/leads/{setup['hot'].id}/summary", headers=setup["h_admin"])
    assert r.status_code == 200
    # mock gateway echoes the rendered CRM summary prompt
    assert "Summarize this lead" in r.json()["text"]


@pytest.mark.asyncio
async def test_list_and_ranking(client: AsyncClient, setup):
    r = await client.get("/api/v1/lead-intelligence/leads", headers=setup["h_admin"],
                         params={"sort": "opportunity"})
    body = r.json()
    assert body["total"] == 3
    # hot high-value lead ranks first by opportunity
    assert body["rows"][0]["lead_id"] == str(setup["hot"].id)
    r = await client.get("/api/v1/lead-intelligence/leads", headers=setup["h_admin"],
                         params={"temperature": "hot"})
    assert all(x["temperature"] == "hot" for x in r.json()["rows"])
    r = await client.get("/api/v1/lead-intelligence/leads", headers=setup["h_admin"],
                         params={"temperature": "cold"})
    assert any(x["lead_id"] == str(setup["cold"].id) for x in r.json()["rows"])


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, setup):
    r = await client.get("/api/v1/lead-intelligence/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["total"] == 3
    assert d["by_temperature"]["hot"] >= 1 and d["by_temperature"]["cold"] >= 1
    assert sum(d["by_quality"].values()) == 3
    assert 0 <= d["avg_completeness"] <= 100 and d["avg_score"] >= 0
    assert len(d["hot_leads"]) >= 1 and d["hot_leads"][0]["lead_id"] == str(setup["hot"].id)
    assert len(d["needs_enrichment"]) >= 1


@pytest.mark.asyncio
async def test_report_and_export(client: AsyncClient, setup):
    r = await client.get("/api/v1/lead-intelligence/report", headers=setup["h_admin"])
    rep = r.json()
    assert rep["total"] == 3
    assert sum(rep["by_temperature"].values()) == 3
    owner = next(o for o in rep["by_owner"] if o["owner_id"] == str(setup["admin"].id))
    assert owner["count"] == 3 and owner["hot"] >= 1
    r = await client.get("/api/v1/lead-intelligence/export", headers=setup["h_admin"])
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("lead_id,name,status") and len(lines) == 4


@pytest.mark.asyncio
async def test_scope_and_not_found(client: AsyncClient, setup):
    # employee owns no leads → empty cohort and 404 on admin's lead
    r = await client.get("/api/v1/lead-intelligence/dashboard", headers=setup["h_emp"])
    assert r.json()["total"] == 0
    r = await client.get(f"/api/v1/lead-intelligence/leads/{setup['hot'].id}", headers=setup["h_emp"])
    assert r.status_code == 404
    r = await client.get(f"/api/v1/lead-intelligence/leads/{uuid.uuid4()}", headers=setup["h_admin"])
    assert r.status_code == 404

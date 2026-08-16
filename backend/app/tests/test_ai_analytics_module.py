import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.ai_platform import AIUsageLog, AIPromptTemplate
from app.models.audit_log import AuditLog
from app.services.ai_analytics_service import percentile, QUALITY_WEIGHTS, LATENCY_SLA_MS
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
    org = await OrganizationRepository(db).create({"name": "AIA Org", "slug": "aia-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@aia.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@aia.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    # a prompt template so prompt-performance can resolve names
    db.add(AIPromptTemplate(organization_id=org.id, key="lead_summary", name="Lead summary",
                            task_type="crm", template="Summarize {{lead}}", created_by=admin.id))
    now = _now()
    # 10 calls by admin: 8 success (fast), 1 slow, 1 failed; 4 use the template
    for i in range(8):
        db.add(AIUsageLog(organization_id=org.id, user_id=admin.id, provider="mock", model="mock-ai",
                          task_type="crm" if i < 5 else "report",
                          template_key="lead_summary" if i < 4 else None,
                          status="success", prompt_tokens=100, completion_tokens=50, total_tokens=150,
                          cost_usd=0.001, latency_ms=200, cache_hit=False, created_at=now - timedelta(hours=i)))
    db.add(AIUsageLog(organization_id=org.id, user_id=admin.id, provider="mock", model="mock-ai",
                      task_type="crm", status="success", prompt_tokens=100, completion_tokens=50,
                      total_tokens=150, cost_usd=0.001, latency_ms=LATENCY_SLA_MS + 4000,
                      cache_hit=False, created_at=now - timedelta(hours=9)))
    db.add(AIUsageLog(organization_id=org.id, user_id=admin.id, provider="mock", model="mock-ai",
                      task_type="crm", status="failed", prompt_tokens=10, completion_tokens=0,
                      total_tokens=10, cost_usd=0, latency_ms=50, cache_hit=False,
                      fallback_from="openai", created_at=now - timedelta(hours=10)))
    # 2 calls by the employee on a different model/provider
    for i in range(2):
        db.add(AIUsageLog(organization_id=org.id, user_id=emp.id, provider="openai", model="gpt-4o",
                          task_type="knowledge", status="success", prompt_tokens=200,
                          completion_tokens=100, total_tokens=300, cost_usd=0.02, latency_ms=900,
                          cache_hit=False, created_at=now - timedelta(hours=i)))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- pure ----------
def test_percentile_is_deterministic():
    vals = [float(i) for i in range(1, 101)]
    assert percentile(vals, 50) == 50.0 or percentile(vals, 50) == 51.0
    assert percentile(vals, 95) == 96.0
    assert percentile([], 95) == 0.0
    assert round(sum(QUALITY_WEIGHTS.values()), 3) == 1.0


# ---------- overview: usage / tokens / cost / success+failure ----------
@pytest.mark.asyncio
async def test_overview(client: AsyncClient, setup):
    r = await client.get("/api/v1/ai-analytics/overview", headers=setup["h_admin"])
    assert r.status_code == 200
    b = r.json()
    assert b["usage"]["requests"] == 12
    assert b["tokens"]["total"] == 8 * 150 + 150 + 10 + 2 * 300  # 1960
    assert b["reliability"]["failed"] == 1
    assert b["reliability"]["success_rate"] == round(11 * 100 / 12, 1)
    assert b["reliability"]["failure_rate"] == round(1 * 100 / 12, 1)
    assert b["cost"]["total_usd"] > 0 and b["cost"]["cost_per_1k_tokens_usd"] > 0
    assert b["usage"]["fallbacks"] == 1


# ---------- latency percentiles ----------
@pytest.mark.asyncio
async def test_latency_percentiles_and_slowest_models(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/latency", headers=setup["h_admin"])).json()
    assert b["samples"] == 11  # successful, non-cached
    assert b["p95_ms"] >= b["p50_ms"]
    assert b["max_ms"] == float(LATENCY_SLA_MS + 4000)
    assert b["within_sla_rate"] < 100.0  # the one slow call
    models = {m["model"] for m in b["slowest_models"]}
    assert "mock-ai" in models and "gpt-4o" in models
    assert isinstance(b["trend"], list)


# ---------- user adoption ----------
@pytest.mark.asyncio
async def test_user_adoption(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/user-adoption", headers=setup["h_admin"])).json()
    assert b["total_active_users"] == 2 and b["ai_users"] == 2
    assert b["adoption_rate"] == 100.0 and b["non_adopters"] == 0
    top = b["top_users"][0]
    assert top["requests"] == 10 and top["user_name"].startswith("Ad")
    assert top["features_used"] >= 2


# ---------- feature adoption ----------
@pytest.mark.asyncio
async def test_feature_adoption(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/feature-adoption", headers=setup["h_admin"])).json()
    feats = {f["feature"]: f for f in b["features"]}
    assert "crm" in feats and "report" in feats and "knowledge" in feats
    assert b["most_used"] == "crm"
    assert feats["knowledge"]["unique_users"] == 1
    assert sum(f["share_pct"] for f in b["features"]) == pytest.approx(100.0, abs=0.5)


# ---------- prompt performance ----------
@pytest.mark.asyncio
async def test_prompt_performance(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/prompt-performance", headers=setup["h_admin"])).json()
    assert b["prompts_used"] == 1
    p = b["prompts"][0]
    assert p["template_key"] == "lead_summary" and p["name"] == "Lead summary"
    assert p["category"] == "crm" and p["requests"] == 4
    assert p["success_rate"] == 100.0 and p["avg_tokens"] == 150.0


# ---------- model performance (per model, not just provider) ----------
@pytest.mark.asyncio
async def test_model_performance(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/model-performance", headers=setup["h_admin"])).json()
    assert b["models_used"] == 2
    by = {m["model"]: m for m in b["models"]}
    assert by["mock-ai"]["requests"] == 10 and by["gpt-4o"]["requests"] == 2
    assert by["mock-ai"]["failure_rate"] == 10.0  # 1 of 10
    assert by["gpt-4o"]["cost_per_1k_tokens_usd"] > 0
    provs = {p["provider"] for p in b["by_provider"]}
    assert provs == {"mock", "openai"}


# ---------- response quality composite ----------
@pytest.mark.asyncio
async def test_quality_composite(client: AsyncClient, setup):
    b = (await client.get("/api/v1/ai-analytics/quality", headers=setup["h_admin"])).json()
    assert 0 <= b["quality_score"] <= 100
    assert b["band"] in ("excellent", "good", "fair", "poor")
    for k in ("success", "no_fallback", "governance_clean", "within_sla"):
        assert k in b["components"]
    assert b["signals"]["failed"] == 1 and b["signals"]["fallbacks"] == 1
    assert b["signals"]["slow_calls"] == 1
    assert "does not grade semantic accuracy" in b["note"]


# ---------- dashboard / report / export / permissions ----------
@pytest.mark.asyncio
async def test_dashboard_report_export_permissions(client: AsyncClient, setup, db: AsyncSession):
    d = (await client.get("/api/v1/ai-analytics/dashboard", headers=setup["h_admin"])).json()
    assert d["requests"] == 12 and d["quality_score"] > 0
    assert d["adoption_rate"] == 100.0 and len(d["top_models"]) == 2

    rep = (await client.get("/api/v1/ai-analytics/report", headers=setup["h_admin"])).json()
    for k in ("overview", "latency", "quality", "user_adoption", "feature_adoption",
              "prompt_performance", "model_performance"):
        assert k in rep

    # every endpoint is manager-gated
    for path in ("dashboard", "overview", "latency", "quality", "user-adoption",
                 "feature-adoption", "prompt-performance", "model-performance", "report", "export"):
        assert (await client.get(f"/api/v1/ai-analytics/{path}",
                                 headers=setup["h_emp"])).status_code == 403

    r = await client.get("/api/v1/ai-analytics/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "lead_summary" in r.text and "gpt-4o" in r.text
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "AI_ANALYTICS_EXPORTED"))).scalars().all()
    assert len(audits) == 1

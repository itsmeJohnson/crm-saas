import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.activity import Activity
from app.models.note import Note
from app.models.ai_platform import AIUsageLog, AICacheEntry
from app.services.ai_gateway_service import AIGatewayService, render_template
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
    org = await OrganizationRepository(db).create({"name": "AI Org", "slug": "ai-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@ai.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@ai.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    lead = Lead(organization_id=org.id, first_name="Ada", last_name="Lovelace", title="t", status="Qualified",
                value=9000, score=70, priority="High", email="ada@x.com", company_name="Analytical Engines",
                assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add(lead)
    await db.flush()
    db.add(Activity(organization_id=org.id, activity_type="Call", subject="Discovery call",
                    description="Asked about pricing tiers", lead_id=lead.id,
                    assigned_user_id=admin.id, created_by=admin.id, call_direction="OUTBOUND"))
    db.add(Note(organization_id=org.id, content="Refund policy: refunds are processed within 14 days of request.",
                created_by=admin.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "lead": lead,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def test_prompt_engine_rendering():
    assert render_template("Hi {{name}}, re {{ goal }}!", {"name": "Ada", "goal": "demo"}) == "Hi Ada, re demo!"
    assert render_template("{{missing}}", {}) == ""


@pytest.mark.asyncio
async def test_generate_via_mock_logs_usage(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"],
                          json={"prompt": "Say hello to the CRM"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"].startswith("[AI mock] Say hello")
    assert body["provider"] == "mock" and body["model"] == "mock-ai"
    assert body["tokens"]["total"] > 0 and body["cached"] is False and body["fallback_used"] is False
    logs = (await db.execute(select(AIUsageLog).filter(
        AIUsageLog.organization_id == setup["org"].id))).scalars().all()
    assert len(logs) == 1 and logs[0].status == "success" and logs[0].provider == "mock"


@pytest.mark.asyncio
async def test_caching(client: AsyncClient, setup, db: AsyncSession):
    payload = {"prompt": "cache me"}
    first = (await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json=payload)).json()
    second = (await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json=payload)).json()
    assert first["cached"] is False and second["cached"] is True
    assert second["text"] == first["text"] and second["cost_usd"] == 0.0
    entries = (await db.execute(select(AICacheEntry).filter(
        AICacheEntry.organization_id == setup["org"].id))).scalars().all()
    assert len(entries) == 1 and entries[0].hits == 1
    cached_logs = (await db.execute(select(AIUsageLog).filter(
        AIUsageLog.organization_id == setup["org"].id, AIUsageLog.cache_hit == True))).scalars().all()
    assert len(cached_logs) == 1 and cached_logs[0].status == "cached"


@pytest.mark.asyncio
async def test_rate_limiting(client: AsyncClient, setup):
    r = await client.patch("/api/v1/ai/settings", headers=setup["h_admin"],
                           json={"daily_request_limit": 1, "cache_enabled": False})
    assert r.status_code == 200
    assert (await client.post("/api/v1/ai/generate", headers=setup["h_admin"],
                              json={"prompt": "one"})).status_code == 200
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "two"})
    assert r.status_code == 429 and "limit" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_budget_cap_and_cost_tracking(client: AsyncClient, setup):
    # a mock provider config with explicit pricing → nonzero cost per call
    r = await client.post("/api/v1/ai/providers", headers=setup["h_admin"], json={
        "provider": "mock", "name": "Priced mock", "default_model": "mock-ai",
        "models": [{"model": "mock-ai", "input_cost_per_1k": 10.0, "output_cost_per_1k": 10.0}]})
    assert r.status_code == 201
    await client.patch("/api/v1/ai/settings", headers=setup["h_admin"],
                       json={"cache_enabled": False, "monthly_budget_usd": 0.01})
    first = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "spend"})
    assert first.status_code == 200 and first.json()["cost_usd"] > 0
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "more"})
    assert r.status_code == 429 and "budget" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fallback_chain(client: AsyncClient, setup, db: AsyncSession):
    # priority 1: unreachable custom endpoint → fails fast; priority 2: mock succeeds
    await client.post("/api/v1/ai/providers", headers=setup["h_admin"], json={
        "provider": "custom", "name": "Broken vLLM", "base_url": "http://127.0.0.1:9/v1",
        "default_model": "broken-model", "priority": 1})
    await client.post("/api/v1/ai/providers", headers=setup["h_admin"], json={
        "provider": "mock", "name": "Mock fallback", "default_model": "mock-ai", "priority": 2})
    await client.patch("/api/v1/ai/settings", headers=setup["h_admin"], json={"cache_enabled": False})
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "resilient"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock" and body["fallback_used"] is True
    logs = (await db.execute(select(AIUsageLog).filter(
        AIUsageLog.organization_id == setup["org"].id).order_by(AIUsageLog.created_at))).scalars().all()
    assert logs[0].provider == "custom" and logs[0].status == "failed"
    assert logs[-1].provider == "mock" and logs[-1].fallback_from == "custom"


@pytest.mark.asyncio
async def test_templates_seeded_and_custom(client: AsyncClient, setup):
    r = await client.get("/api/v1/ai/templates", headers=setup["h_admin"])
    keys = {t["key"] for t in r.json()}
    for k in ("crm_record_summary", "crm_email_draft", "report_narrative", "reply_draft",
              "kb_answer", "text_summary"):
        assert k in keys
    r = await client.post("/api/v1/ai/templates", headers=setup["h_admin"], json={
        "key": "greeting", "name": "Greeting", "template": "Greet {{who}} warmly."})
    assert r.status_code == 201
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={
        "template_key": "greeting", "variables": {"who": "Johnson"}})
    assert "Greet Johnson warmly." in r.json()["text"]
    r = await client.get("/api/v1/ai/templates", headers=setup["h_admin"])
    tpl = next(t for t in r.json() if t["key"] == "greeting")
    assert tpl["usage_count"] == 1


@pytest.mark.asyncio
async def test_chat_conversation_memory(client: AsyncClient, setup):
    r = await client.post("/api/v1/ai/chat", headers=setup["h_admin"],
                          json={"message": "Remember the number 42."})
    assert r.status_code == 200
    convo_id = r.json()["conversation_id"]
    assert convo_id
    r = await client.post("/api/v1/ai/chat", headers=setup["h_admin"],
                          json={"message": "What number?", "conversation_id": convo_id})
    assert r.status_code == 200
    r = await client.get(f"/api/v1/ai/conversations/{convo_id}/messages", headers=setup["h_admin"])
    msgs = r.json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    r = await client.get("/api/v1/ai/conversations", headers=setup["h_admin"])
    convo = next(c for c in r.json() if c["id"] == convo_id)
    assert convo["message_count"] == 4 and convo["title"].startswith("Remember the number")


@pytest.mark.asyncio
async def test_context_manager_crm_integration(client: AsyncClient, setup):
    r = await client.post("/api/v1/ai/crm/summarize", headers=setup["h_admin"],
                          json={"context_type": "lead", "context_id": str(setup["lead"].id)})
    assert r.status_code == 200
    assert "Summarize this lead" in r.json()["text"]  # mock echoes the rendered prompt
    r = await client.post("/api/v1/ai/crm/draft-email", headers=setup["h_admin"],
                          json={"context_type": "lead", "context_id": str(setup["lead"].id),
                                "goal": "book a demo"})
    assert r.status_code == 200 and "Ada Lovelace" in r.json()["text"]
    r = await client.post("/api/v1/ai/crm/summarize", headers=setup["h_admin"],
                          json={"context_type": "lead", "context_id": str(uuid.uuid4())})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_report_communication_kb_document_integrations(client: AsyncClient, setup, db: AsyncSession):
    # Reports
    r = await client.post("/api/v1/report-builder", json={
        "name": "AI leads report", "dataset": "leads",
        "columns": [{"field": "status"}, {"field": "value"}]}, headers=setup["h_admin"])
    report_id = r.json()["id"]
    r = await client.post(f"/api/v1/ai/reports/{report_id}/narrative", headers=setup["h_admin"])
    assert r.status_code == 200 and "AI leads report" in r.json()["text"]
    # Communication
    act = (await db.execute(select(Activity).filter(
        Activity.organization_id == setup["org"].id))).scalars().first()
    r = await client.post(f"/api/v1/ai/communication/{act.id}/draft-reply", headers=setup["h_admin"])
    assert r.status_code == 200 and r.json()["task_type"] == "communication"
    # Knowledge base (grounded in the seeded note)
    r = await client.post("/api/v1/ai/knowledge/ask", headers=setup["h_admin"],
                          json={"question": "What is our refund policy?"})
    assert r.status_code == 200 and "refund" in r.json()["text"].lower()
    # Documents
    r = await client.post("/api/v1/ai/documents/summarize", headers=setup["h_admin"],
                          json={"text": "A long document about quarterly performance.", "length": 3})
    assert r.status_code == 200 and r.json()["task_type"] == "document"
    logs = (await db.execute(select(AIUsageLog).filter(
        AIUsageLog.organization_id == setup["org"].id))).scalars().all()
    assert {"report", "communication", "knowledge", "document"} <= {l.task_type for l in logs}


@pytest.mark.asyncio
async def test_queue_automation_integration(client: AsyncClient, setup, db: AsyncSession):
    out = await AIGatewayService(db).run_automation_task(setup["org"].id, {"prompt": "automate this"})
    assert out["model"] == "mock-ai" and out["completion"].startswith("[AI mock] automate this")
    assert out["tokens"] > 0 and out["provider"] == "mock"
    log = (await db.execute(select(AIUsageLog).filter(
        AIUsageLog.organization_id == setup["org"].id,
        AIUsageLog.task_type == "automation"))).scalars().first()
    assert log is not None


@pytest.mark.asyncio
async def test_streaming(client: AsyncClient, setup):
    r = await client.post("/api/v1/ai/generate/stream", headers=setup["h_admin"],
                          json={"prompt": "stream me"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert 'data: {"delta"' in body and "data: [DONE]" in body
    assert "stream" in body  # mock echoes the prompt in chunks


@pytest.mark.asyncio
async def test_provider_admin_and_masking(client: AsyncClient, setup):
    r = await client.post("/api/v1/ai/providers", headers=setup["h_admin"], json={
        "provider": "anthropic", "name": "Claude", "api_key": "sk-ant-secret1234",
        "default_model": "claude-haiku-4-5", "priority": 1})
    assert r.status_code == 201
    body = r.json()
    assert body["api_key"] == "…1234"  # masked
    bad = await client.post("/api/v1/ai/providers", headers=setup["h_admin"],
                            json={"provider": "skynet", "default_model": "x"})
    assert bad.status_code == 400
    # test-connection endpoint returns a structured result (fails: fake key)
    r = await client.post(f"/api/v1/ai/providers/{body['id']}/test", headers=setup["h_admin"])
    assert r.status_code == 200 and r.json()["status"] in ("success", "failed")


@pytest.mark.asyncio
async def test_usage_dashboard_monitoring(client: AsyncClient, setup):
    await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "a"})
    await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "a"})  # cache hit
    r = await client.get("/api/v1/ai/usage/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["requests"] == 2 and d["cached"] == 1 and d["cache_hit_rate"] == 50.0
    assert "mock" in d["by_provider"] and d["budget"]["monthly_budget_usd"] == 100.0
    r = await client.get("/api/v1/ai/usage/logs", headers=setup["h_admin"])
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_permissions(client: AsyncClient, setup):
    # every active user may use the gateway…
    r = await client.post("/api/v1/ai/generate", headers=setup["h_emp"], json={"prompt": "hello"})
    assert r.status_code == 200
    # …but administration and monitoring are manager/admin only
    for method, path in (("GET", "/api/v1/ai/settings"), ("GET", "/api/v1/ai/providers"),
                         ("GET", "/api/v1/ai/usage/dashboard")):
        resp = await client.request(method, path, headers=setup["h_emp"])
        assert resp.status_code == 403, path


@pytest.mark.asyncio
async def test_ai_disabled_gate(client: AsyncClient, setup):
    await client.patch("/api/v1/ai/settings", headers=setup["h_admin"], json={"is_enabled": False})
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={"prompt": "x"})
    assert r.status_code == 403 and "disabled" in r.json()["detail"].lower()

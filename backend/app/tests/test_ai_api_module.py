import json
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.ai_api import AIApiKey, AIApiRequest, AIWebhook, AIWebhookDelivery
from app.models.audit_log import AuditLog
from app.services.ai_api_service import (AIApiService, build_signature_header, verify_signature,
                                         generate_key, hash_key, SCOPES, WEBHOOK_EVENTS,
                                         CURRENT_VERSION)
from app.services.ai_sdk_templates import SDK_LANGUAGES, render_sdk, render_examples
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


@pytest.fixture(autouse=True)
def no_outbound_webhooks(monkeypatch):
    """Webhook delivery must never hit the network in tests. Records every
    signed POST so assertions can inspect headers and body."""
    sent: list[dict] = []

    class _Resp:
        def __init__(self, code): self.status_code = code

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, content=None, headers=None):
            sent.append({"url": url, "body": content, "headers": headers or {}})
            return _Resp(500 if "fail" in url else 200)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return sent


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Dev Org", "slug": "dev-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@devapi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@devapi.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


async def _make_key(client: AsyncClient, setup, **overrides) -> dict:
    body = {"name": "Integration key", **overrides}
    r = await client.post("/api/v1/ai-developer/keys", headers=setup["h_admin"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _key_headers(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


# ---------- pure helpers ----------
def test_key_generation_and_hashing():
    raw, prefix, digest = generate_key("live")
    assert raw.startswith("crm_live_") and raw.startswith(prefix)
    assert digest == hash_key(raw) and len(digest) == 64
    # a second key never collides
    assert generate_key("test")[0] != raw
    assert generate_key("test")[0].startswith("crm_test_")


def test_signature_round_trip():
    body = json.dumps({"type": "ai.webhook.test"}, separators=(",", ":"))
    header = build_signature_header("s3cr3t", body)
    assert verify_signature("s3cr3t", header, body) is True
    assert verify_signature("wrong", header, body) is False
    assert verify_signature("s3cr3t", header, body + "x") is False
    # replayed timestamps outside the tolerance window are rejected
    old = build_signature_header("s3cr3t", body, timestamp=int(time.time()) - 4000)
    assert verify_signature("s3cr3t", old, body) is False
    assert verify_signature("s3cr3t", "garbage", body) is False


def test_sdks_render_for_every_language():
    for lang in SDK_LANGUAGES:
        src = render_sdk(lang, "https://api.test/api/v1/ai-api", CURRENT_VERSION)
        assert "https://api.test/api/v1/ai-api" in src
        assert "generate" in src and "stream" in src
        # no provider is ever hardcoded into a client
        for banned in ("api.openai.com", "anthropic.com", "generativelanguage"):
            assert banned not in src
    # the Python SDK is real, importable source
    compile(render_sdk("python", "https://api.test", CURRENT_VERSION), "crm_ai.py", "exec")


def test_examples_cover_every_language():
    ex = render_examples("https://api.test/api/v1/ai-api")
    langs = {e["language"] for e in ex}
    assert {"bash", "python", "javascript", "java"} <= langs
    assert any("verify_webhook" in e["code"] for e in ex)


# ---------- key management + permissions ----------
@pytest.mark.asyncio
async def test_key_lifecycle_and_permissions(client: AsyncClient, setup, db: AsyncSession):
    created = await _make_key(client, setup, scopes=["ai:generate", "ai:usage"], daily_quota=50)
    assert created["api_key"].startswith("crm_live_")
    assert created["scopes"] == ["ai:generate", "ai:usage"]
    assert created["daily_quota"] == 50

    listed = (await client.get("/api/v1/ai-developer/keys", headers=setup["h_admin"])).json()
    assert len(listed) == 1
    # the raw secret is never readable again
    assert "api_key" not in listed[0]
    assert listed[0]["masked_key"].startswith("crm_live_")

    # only the hash is persisted
    row = (await db.execute(select(AIApiKey).filter(AIApiKey.id == uuid.UUID(created["id"])))).scalars().first()
    assert row.key_hash == hash_key(created["api_key"]) and created["api_key"] not in row.key_prefix + row.key_hash

    upd = (await client.patch(f"/api/v1/ai-developer/keys/{created['id']}", headers=setup["h_admin"],
                              json={"rate_limit_per_min": 5})).json()
    assert upd["rate_limit_per_min"] == 5

    rotated = (await client.post(f"/api/v1/ai-developer/keys/{created['id']}/rotate",
                                 headers=setup["h_admin"])).json()
    assert rotated["api_key"] != created["api_key"]

    # employees cannot manage developer access
    assert (await client.get("/api/v1/ai-developer/keys", headers=setup["h_emp"])).status_code == 403
    assert (await client.post("/api/v1/ai-developer/keys", headers=setup["h_emp"],
                              json={"name": "nope"})).status_code == 403

    # unknown scopes are rejected
    assert (await client.post("/api/v1/ai-developer/keys", headers=setup["h_admin"],
                              json={"name": "bad", "scopes": ["ai:everything"]})).status_code == 400

    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "AI_API_KEY_CREATED"))).scalars().all()
    assert len(audits) == 1


# ---------- authentication ----------
@pytest.mark.asyncio
async def test_public_api_requires_a_valid_key(client: AsyncClient, setup):
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"})).status_code == 401
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"},
                              headers=_key_headers("crm_live_nonsense"))).status_code == 401

    created = await _make_key(client, setup)
    # both accepted auth schemes work
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"},
                              headers=_key_headers(created["api_key"]))).status_code == 200
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"},
                              headers={"X-API-Key": created["api_key"]})).status_code == 200

    # a revoked key stops working immediately
    await client.post(f"/api/v1/ai-developer/keys/{created['id']}/revoke", headers=setup["h_admin"])
    r = await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"},
                          headers=_key_headers(created["api_key"]))
    assert r.status_code == 401 and "revoked" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scopes_are_enforced(client: AsyncClient, setup):
    created = await _make_key(client, setup, scopes=["ai:generate"])
    h = _key_headers(created["api_key"])
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"}, headers=h)).status_code == 200
    r = await client.post("/api/v1/ai-api/chat", json={"message": "hi"}, headers=h)
    assert r.status_code == 403 and "ai:chat" in r.json()["detail"]
    assert (await client.get("/api/v1/ai-api/models", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_provider_allowlist_is_enforced(client: AsyncClient, setup):
    created = await _make_key(client, setup, allowed_providers=["openai"])
    r = await client.post("/api/v1/ai-api/generate", json={"prompt": "hi", "provider": "mock"},
                          headers=_key_headers(created["api_key"]))
    assert r.status_code == 403 and "provider" in r.json()["detail"].lower()


# ---------- generate / chat / stream ----------
@pytest.mark.asyncio
async def test_generate_chat_and_stream_through_the_gateway(client: AsyncClient, setup, db: AsyncSession):
    created = await _make_key(client, setup)
    h = _key_headers(created["api_key"])

    r = await client.post("/api/v1/ai-api/generate", json={"prompt": "Summarise this lead"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["text"] and body["provider"] and body["model"]
    assert r.headers["X-API-Version"] == CURRENT_VERSION
    assert int(r.headers["X-RateLimit-Remaining"]) < int(r.headers["X-RateLimit-Limit"])

    c = await client.post("/api/v1/ai-api/chat", json={"message": "Hello there"}, headers=h)
    assert c.status_code == 200 and c.json()["conversation_id"]
    follow = await client.post("/api/v1/ai-api/chat", headers=h, json={
        "message": "And next?", "conversation_id": c.json()["conversation_id"]})
    assert follow.status_code == 200
    assert follow.json()["conversation_id"] == c.json()["conversation_id"]

    s = await client.post("/api/v1/ai-api/stream", json={"prompt": "stream please"}, headers=h)
    assert s.status_code == 200
    assert s.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in s.text

    # every call landed in the request ledger
    rows = (await db.execute(select(AIApiRequest).filter(
        AIApiRequest.organization_id == setup["org"].id))).scalars().all()
    assert {r.endpoint for r in rows} == {"generate", "chat", "stream"}
    assert all(r.api_version == CURRENT_VERSION for r in rows)


# ---------- rate limits + quota ----------
@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_retry_after(client: AsyncClient, setup, db: AsyncSession):
    created = await _make_key(client, setup, rate_limit_per_min=2)
    h = _key_headers(created["api_key"])
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "a"}, headers=h)).status_code == 200
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "b"}, headers=h)).status_code == 200
    r = await client.post("/api/v1/ai-api/generate", json={"prompt": "c"}, headers=h)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert "rate limit" in r.json()["detail"].lower()
    # the throttled call is still recorded so developers can see it
    throttled = (await db.execute(select(AIApiRequest).filter(
        AIApiRequest.status_code == 429))).scalars().all()
    assert len(throttled) == 1


@pytest.mark.asyncio
async def test_daily_quota_exhaustion(client: AsyncClient, setup):
    created = await _make_key(client, setup, daily_quota=1, rate_limit_per_min=100)
    h = _key_headers(created["api_key"])
    assert (await client.post("/api/v1/ai-api/generate", json={"prompt": "a"}, headers=h)).status_code == 200
    r = await client.post("/api/v1/ai-api/generate", json={"prompt": "b"}, headers=h)
    assert r.status_code == 429 and "quota" in r.json()["detail"].lower()


# ---------- discovery / models / templates / usage ----------
@pytest.mark.asyncio
async def test_version_models_templates_and_usage(client: AsyncClient, setup):
    v = await client.get("/api/v1/ai-api/version")
    assert v.status_code == 200 and v.json()["current_version"] == CURRENT_VERSION
    assert v.headers["X-API-Version"] == CURRENT_VERSION

    spec = (await client.get("/api/v1/ai-api/openapi.json")).json()
    assert spec["openapi"].startswith("3.1")
    assert "/generate" in spec["paths"] and "ApiKeyAuth" in spec["components"]["securitySchemes"]

    created = await _make_key(client, setup)
    h = _key_headers(created["api_key"])

    m = (await client.get("/api/v1/ai-api/models", headers=h)).json()
    assert m["providers"] and m["default_provider"] and m["fallback_chain"]

    t = await client.get("/api/v1/ai-api/templates", headers=h)
    assert t.status_code == 200 and isinstance(t.json(), list)

    await client.post("/api/v1/ai-api/generate", json={"prompt": "hello"}, headers=h)
    u = (await client.get("/api/v1/ai-api/usage", headers=h)).json()
    assert u["requests"] >= 1 and u["rate_limit"]["quota"] == created["daily_quota"]
    assert u["by_endpoint"]["generate"] >= 1


# ---------- webhooks ----------
@pytest.mark.asyncio
async def test_webhook_signed_delivery_and_events(client: AsyncClient, setup, no_outbound_webhooks,
                                                  db: AsyncSession):
    w = (await client.post("/api/v1/ai-developer/webhooks", headers=setup["h_admin"], json={
        "name": "My sink", "url": "https://hooks.test/ai",
        "events": ["ai.generation.completed"]})).json()
    assert w["secret"] and len(w["secret"]) > 10

    created = await _make_key(client, setup)
    await client.post("/api/v1/ai-api/generate", json={"prompt": "hi"},
                      headers=_key_headers(created["api_key"]))

    assert len(no_outbound_webhooks) >= 1
    sent = no_outbound_webhooks[-1]
    assert sent["url"] == "https://hooks.test/ai"
    assert sent["headers"]["X-CRM-AI-Event"] == "ai.generation.completed"
    assert verify_signature(w["secret"], sent["headers"]["X-CRM-AI-Signature"], sent["body"]) is True
    payload = json.loads(sent["body"])
    assert payload["type"] == "ai.generation.completed" and payload["api_version"] == CURRENT_VERSION

    d = (await client.get("/api/v1/ai-developer/webhooks/deliveries", headers=setup["h_admin"])).json()
    assert d and d[0]["status"] == "success"

    # this hook is not subscribed to key events, so nothing new is sent
    before = len(no_outbound_webhooks)
    await client.post("/api/v1/ai-developer/keys", headers=setup["h_admin"], json={"name": "Second"})
    assert len(no_outbound_webhooks) == before


@pytest.mark.asyncio
async def test_webhook_failure_retries_then_dead_letters(client: AsyncClient, setup,
                                                         no_outbound_webhooks, db: AsyncSession):
    w = (await client.post("/api/v1/ai-developer/webhooks", headers=setup["h_admin"], json={
        "name": "Broken", "url": "https://hooks.test/fail", "max_attempts": 2})).json()
    t = (await client.post(f"/api/v1/ai-developer/webhooks/{w['id']}/test",
                           headers=setup["h_admin"])).json()
    assert t["status"] == "failed" and t["attempts"] == 1 and t["next_retry_at"]

    # force the backoff to be due, then run the cron step
    row = (await db.execute(select(AIWebhookDelivery).filter(
        AIWebhookDelivery.id == uuid.UUID(t["id"])))).scalars().first()
    from app.services.ai_api_service import _now
    from datetime import timedelta
    row.next_retry_at = _now() - timedelta(minutes=1)
    db.add(row)
    await db.commit()

    out = await AIApiService(db).retry_due_deliveries(setup["org"].id)
    await db.commit()
    assert out["attempted"] == 1 and out["dead_lettered"] == 1
    await db.refresh(row)
    assert row.status == "dead_letter" and row.attempts == 2


@pytest.mark.asyncio
async def test_webhook_validation_and_permissions(client: AsyncClient, setup):
    bad = await client.post("/api/v1/ai-developer/webhooks", headers=setup["h_admin"], json={
        "name": "Bad", "url": "ftp://nope"})
    assert bad.status_code == 400
    bad_event = await client.post("/api/v1/ai-developer/webhooks", headers=setup["h_admin"], json={
        "name": "Bad", "url": "https://ok.test", "events": ["ai.does.not.exist"]})
    assert bad_event.status_code == 400
    assert (await client.get("/api/v1/ai-developer/webhooks", headers=setup["h_emp"])).status_code == 403


# ---------- developer portal / docs / analytics ----------
@pytest.mark.asyncio
async def test_portal_docs_sdk_and_analytics(client: AsyncClient, setup):
    created = await _make_key(client, setup)
    await client.post("/api/v1/ai-api/generate", json={"prompt": "hello"},
                      headers=_key_headers(created["api_key"]))

    p = (await client.get("/api/v1/ai-developer/portal", headers=setup["h_admin"],
                          params={"base_url": "https://crm.test/api/v1/ai-api"})).json()
    assert p["keys_total"] == 1 and p["keys_active"] == 1
    assert p["requests_30d"] >= 1 and p["success_rate"] == 100.0
    assert p["base_url"] == "https://crm.test/api/v1/ai-api"
    assert {s["key"] for s in p["sdk_languages"]} == set(SDK_LANGUAGES)

    docs = (await client.get("/api/v1/ai-developer/docs", headers=setup["h_admin"])).json()
    assert docs["version"] == CURRENT_VERSION
    assert {e["path"] for e in docs["endpoints"]} >= {"/generate", "/chat", "/stream"}
    assert len(docs["scopes"]) == len(SCOPES)
    assert len(docs["webhooks"]["events"]) == len(WEBHOOK_EVENTS)

    ex = (await client.get("/api/v1/ai-developer/examples", headers=setup["h_admin"])).json()
    assert len(ex) >= 5

    langs = (await client.get("/api/v1/ai-developer/sdk", headers=setup["h_admin"])).json()
    assert {l["key"] for l in langs} == set(SDK_LANGUAGES)
    py = (await client.get("/api/v1/ai-developer/sdk/python", headers=setup["h_admin"])).json()
    assert py["filename"] == "crm_ai.py" and "class CRMAIClient" in py["source"]
    dl = await client.get("/api/v1/ai-developer/sdk/java/download", headers=setup["h_admin"])
    assert dl.status_code == 200 and "CrmAiClient.java" in dl.headers["content-disposition"]
    assert (await client.get("/api/v1/ai-developer/sdk/cobol", headers=setup["h_admin"])).status_code == 404

    a = (await client.get("/api/v1/ai-developer/analytics", headers=setup["h_admin"])).json()
    assert a["requests"] >= 1 and a["by_endpoint"]["generate"]["requests"] >= 1
    assert a["by_key"]["Integration key"]["requests"] >= 1

    logs = (await client.get("/api/v1/ai-developer/requests", headers=setup["h_admin"])).json()
    assert logs and logs[0]["endpoint"] == "generate"

    csv_out = await client.get("/api/v1/ai-developer/export", headers=setup["h_admin"])
    assert csv_out.status_code == 200 and "Section" in csv_out.text

    assert (await client.get("/api/v1/ai-developer/portal", headers=setup["h_emp"])).status_code == 403
    assert (await client.get("/api/v1/ai-developer/analytics", headers=setup["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_catalog_lists_scopes_events_and_versions(client: AsyncClient, setup):
    c = (await client.get("/api/v1/ai-developer/catalog", headers=setup["h_admin"])).json()
    assert {s["key"] for s in c["scopes"]} == set(SCOPES)
    assert {e["key"] for e in c["webhook_events"]} == set(WEBHOOK_EVENTS)
    assert c["current_version"] == CURRENT_VERSION
    assert c["versions"][0]["status"] == "stable"
    assert c["environments"] == ["live", "test"]

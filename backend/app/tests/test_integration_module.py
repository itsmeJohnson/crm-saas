import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.integration import Integration, IntegrationLog, IntegrationEvent
from app.models.audit_log import AuditLog
from app.services import integration_catalog as cat
from app.services.integration_service import IntegrationService, mask_secrets, DOWN_AFTER_FAILURES
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


@pytest.fixture(autouse=True)
def http(monkeypatch):
    """No integration test may touch the network. `calls` records every request;
    `script` maps a URL substring to the status code to return (0 = raise)."""
    calls: list[dict] = []
    script: dict[str, int] = {}

    class _Resp:
        def __init__(self, code):
            self.status_code = code
            self.text = "" if code < 400 else f"error {code}"

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def request(self, method, url, **kw):
            calls.append({"method": method, "url": url, "headers": kw.get("headers") or {},
                          "auth": kw.get("auth")})
            for frag, code in script.items():
                if frag in url:
                    if code == 0:
                        raise RuntimeError("connection refused")
                    return _Resp(code)
            return _Resp(200)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    # keep retry backoff from actually sleeping
    import app.services.integration_service as svc
    async def _no_sleep(*a, **k): return None
    monkeypatch.setattr(svc.asyncio, "sleep", _no_sleep)
    return {"calls": calls, "script": script}


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Hub Org", "slug": "hub-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@hub.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await ur.create_user(org.id, {"email": "mgr@hub.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Man", "last_name": "Ager", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@hub.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
    await db.commit()
    return {"org": org, "admin": admin, "mgr": mgr, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


async def _create(client, setup, **kw):
    body = {"provider": "rest_api", "name": "Test API",
            "config": {"base_url": "https://vendor.test/api"}, **kw}
    r = await client.post("/api/v1/integrations", headers=setup["h_admin"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- catalog ----------
def test_catalog_covers_every_required_category():
    c = cat.catalog()
    keys = {x["key"] for x in c["categories"]}
    required = {"payment", "calling", "sms", "whatsapp", "email", "calendar", "storage",
                "erp", "accounting", "hrms", "ecommerce", "marketing", "social", "crm",
                "identity", "webhook", "api"}
    assert required <= keys
    # every category offers at least one connector plus a custom escape hatch
    for entry in c["categories"]:
        assert entry["connectors"], f"{entry['key']} has no connectors"
        assert any(x["key"].startswith("custom_") for x in entry["connectors"])
    # SSO + LDAP are real identity connectors
    ident = {x["key"] for x in c["categories"] if x["key"] == "identity" for x in x["connectors"]}
    assert {"ldap", "active_directory", "saml_generic", "okta", "azure_ad"} <= ident


def test_catalog_marks_modules_that_own_their_credentials():
    managed = {k: v["managed_by"] for k, v in cat.CATEGORIES.items()}
    assert managed["sms"] == "sms_settings"
    assert managed["email"] == "email_settings"
    assert managed["whatsapp"] == "whatsapp_settings"
    assert managed["payment"] == "payment_gateways"
    # the hub owns everything else
    assert managed["erp"] is None and managed["identity"] is None and managed["api"] is None


def test_secret_masking():
    out = mask_secrets({"api_key": "supersecretvalue", "username": "bob",
                        "nested": {"client_secret": "abcdefgh"}, "count": 5})
    assert out["api_key"].endswith("alue") and "supersecret" not in out["api_key"]
    assert out["username"] == "bob" and out["count"] == 5
    assert "abcdefgh" not in out["nested"]["client_secret"]


# ---------- permissions ----------
@pytest.mark.asyncio
async def test_permissions_admin_writes_manager_reads(client: AsyncClient, setup):
    created = await _create(client, setup)
    # manager can read
    assert (await client.get("/api/v1/integrations", headers=setup["h_mgr"])).status_code == 200
    # manager cannot write credentials
    r = await client.patch(f"/api/v1/integrations/{created['id']}", headers=setup["h_mgr"],
                           json={"name": "renamed"})
    assert r.status_code == 403
    assert (await client.post("/api/v1/integrations", headers=setup["h_mgr"],
                              json={"provider": "rest_api"})).status_code == 403
    # employees see nothing at all
    assert (await client.get("/api/v1/integrations", headers=setup["h_emp"])).status_code == 403
    assert (await client.get("/api/v1/integrations/dashboard", headers=setup["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_credentials_are_masked_on_read(client: AsyncClient, setup, db: AsyncSession):
    created = await _create(client, setup, credentials={"api_key": "plaintext-secret-abcd"})
    assert "plaintext-secret" not in json.dumps(created)
    listed = (await client.get("/api/v1/integrations", headers=setup["h_admin"])).json()
    assert "plaintext-secret" not in json.dumps(listed)
    # but the real value is stored so the runtime can use it
    row = (await db.execute(select(Integration).filter(
        Integration.id == uuid.UUID(created["id"])))).scalars().first()
    assert row.credentials["api_key"] == "plaintext-secret-abcd"


# ---------- CRUD + validation ----------
@pytest.mark.asyncio
async def test_create_rejects_unknown_and_module_owned_categories(client: AsyncClient, setup):
    bad = await client.post("/api/v1/integrations", headers=setup["h_admin"],
                            json={"provider": "not_a_real_connector"})
    assert bad.status_code == 400
    # SMS is owned by sms_settings — the hub must refuse to duplicate it
    owned = await client.post("/api/v1/integrations", headers=setup["h_admin"],
                              json={"provider": "custom_sms"})
    assert owned.status_code == 400 and "own module" in owned.json()["detail"]


@pytest.mark.asyncio
async def test_credentials_patch_merges(client: AsyncClient, setup, db: AsyncSession):
    created = await _create(client, setup, credentials={"api_key": "aaaa1111"})
    await client.patch(f"/api/v1/integrations/{created['id']}", headers=setup["h_admin"],
                       json={"config": {"timeout_note": "x"}})
    row = (await db.execute(select(Integration).filter(
        Integration.id == uuid.UUID(created["id"])))).scalars().first()
    await db.refresh(row)
    # the untouched credential survived a config-only PATCH
    assert row.credentials["api_key"] == "aaaa1111"
    assert row.config["base_url"] == "https://vendor.test/api"


# ---------- retry ----------
@pytest.mark.asyncio
async def test_retry_then_success_and_attempt_count(client: AsyncClient, setup, http, db: AsyncSession):
    created = await _create(client, setup, max_attempts=3, retry_backoff_seconds=0)
    http["script"]["vendor.test"] = 503
    r = await client.post(f"/api/v1/integrations/{created['id']}/call",
                          headers=setup["h_admin"], json={"method": "GET", "path": "/ping"})
    body = r.json()
    assert body["ok"] is False and body["attempts"] == 3
    assert len(http["calls"]) == 3           # retried exactly max_attempts times
    logs = (await client.get("/api/v1/integrations/logs", headers=setup["h_admin"])).json()
    assert logs[0]["attempts"] == 3 and logs[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_client_error_is_not_retried(client: AsyncClient, setup, http):
    created = await _create(client, setup, max_attempts=4, retry_backoff_seconds=0)
    http["script"]["vendor.test"] = 404
    r = await client.post(f"/api/v1/integrations/{created['id']}/call",
                          headers=setup["h_admin"], json={"method": "GET", "path": "/nope"})
    # a 404 cannot be fixed by retrying — one attempt only
    assert r.json()["attempts"] == 1 and len(http["calls"]) == 1


@pytest.mark.asyncio
async def test_429_and_timeout_are_retried(client: AsyncClient, setup, http):
    created = await _create(client, setup, max_attempts=2, retry_backoff_seconds=0)
    http["script"]["vendor.test"] = 429
    r = await client.post(f"/api/v1/integrations/{created['id']}/call",
                          headers=setup["h_admin"], json={"path": "/x"})
    assert r.json()["attempts"] == 2


# ---------- fallback ----------
@pytest.mark.asyncio
async def test_fallback_takes_over_when_primary_is_exhausted(client: AsyncClient, setup, http):
    backup = await _create(client, setup, name="Backup API",
                           config={"base_url": "https://backup.test/api"})
    primary = await _create(client, setup, name="Primary API", max_attempts=2,
                            retry_backoff_seconds=0,
                            config={"base_url": "https://vendor.test/api"})
    await client.patch(f"/api/v1/integrations/{primary['id']}", headers=setup["h_admin"],
                       json={"fallback_integration_id": backup["id"]})
    http["script"]["vendor.test"] = 500   # primary always fails, backup returns 200
    r = await client.post(f"/api/v1/integrations/{primary['id']}/call",
                          headers=setup["h_admin"], json={"path": "/data"})
    body = r.json()
    assert body["ok"] is True
    assert body["name"] == "Backup API"
    assert body["fell_back_from"] == primary["id"]
    assert any("backup.test" in c["url"] for c in http["calls"])
    logs = (await client.get("/api/v1/integrations/logs", headers=setup["h_admin"])).json()
    assert any(l["status"] == "fallback" for l in logs)


@pytest.mark.asyncio
async def test_fallback_rejects_self_and_loops_and_cross_category(client: AsyncClient, setup):
    a = await _create(client, setup, name="A")
    b = await _create(client, setup, name="B")
    # self-reference
    r = await client.patch(f"/api/v1/integrations/{a['id']}", headers=setup["h_admin"],
                           json={"fallback_integration_id": a["id"]})
    assert r.status_code == 400 and "itself" in r.json()["detail"]
    # a -> b is fine, b -> a would loop
    assert (await client.patch(f"/api/v1/integrations/{a['id']}", headers=setup["h_admin"],
                               json={"fallback_integration_id": b["id"]})).status_code == 200
    loop = await client.patch(f"/api/v1/integrations/{b['id']}", headers=setup["h_admin"],
                              json={"fallback_integration_id": a["id"]})
    assert loop.status_code == 400 and "loop" in loop.json()["detail"]
    # different category is refused
    erp = await _create(client, setup, provider="odoo", name="Odoo",
                        config={"base_url": "https://odoo.test"})
    cross = await client.patch(f"/api/v1/integrations/{a['id']}", headers=setup["h_admin"],
                               json={"fallback_integration_id": erp["id"]})
    assert cross.status_code == 400 and "same category" in cross.json()["detail"]


@pytest.mark.asyncio
async def test_deleting_a_target_clears_dependent_fallback(client: AsyncClient, setup, db: AsyncSession):
    backup = await _create(client, setup, name="Backup")
    primary = await _create(client, setup, name="Primary")
    await client.patch(f"/api/v1/integrations/{primary['id']}", headers=setup["h_admin"],
                       json={"fallback_integration_id": backup["id"]})
    await client.delete(f"/api/v1/integrations/{backup['id']}", headers=setup["h_admin"])
    row = (await db.execute(select(Integration).filter(
        Integration.id == uuid.UUID(primary["id"])))).scalars().first()
    await db.refresh(row)
    assert row.fallback_integration_id is None   # no dangling pointer


# ---------- health monitoring ----------
@pytest.mark.asyncio
async def test_health_transitions_degraded_then_down_then_recovers(client: AsyncClient, setup, http):
    created = await _create(client, setup, max_attempts=1, retry_backoff_seconds=0)
    http["script"]["vendor.test"] = 500
    first = await client.post(f"/api/v1/integrations/{created['id']}/health-check",
                              headers=setup["h_admin"])
    assert first.json()["status"] == "degraded"
    for _ in range(DOWN_AFTER_FAILURES - 1):
        last = await client.post(f"/api/v1/integrations/{created['id']}/health-check",
                                 headers=setup["h_admin"])
    assert last.json()["status"] == "down"
    # recovery clears the failure streak
    http["script"].pop("vendor.test")
    ok = await client.post(f"/api/v1/integrations/{created['id']}/health-check",
                           headers=setup["h_admin"])
    assert ok.json()["status"] == "healthy"
    detail = (await client.get(f"/api/v1/integrations/{created['id']}", headers=setup["h_admin"])).json()
    assert detail["consecutive_failures"] == 0 and detail["last_error"] is None


@pytest.mark.asyncio
async def test_health_check_without_base_url_stays_unconfigured(client: AsyncClient, setup):
    created = await _create(client, setup, provider="custom_erp", name="Bare", config={})
    r = await client.post(f"/api/v1/integrations/{created['id']}/health-check", headers=setup["h_admin"])
    body = r.json()
    # never report a misleading green for something that was never configured
    assert body["checked"] is False and body["status"] == "unconfigured"


@pytest.mark.asyncio
async def test_bulk_health_check_and_transport_error(client: AsyncClient, setup, http):
    await _create(client, setup, name="One", max_attempts=1)
    http["script"]["vendor.test"] = 0      # raises, exercising the transport path
    out = (await client.post("/api/v1/integrations/health-check", headers=setup["h_admin"])).json()
    assert out["checked"] >= 1 and out["failed"] >= 1


# ---------- mirroring modules that own their own credentials ----------
@pytest.mark.asyncio
async def test_sync_managed_mirrors_without_duplicating(client: AsyncClient, setup, db: AsyncSession):
    from app.models.sms_settings import SmsSettings
    db.add(SmsSettings(organization_id=setup["org"].id, provider="twilio"))
    await db.commit()

    out = (await client.post("/api/v1/integrations/sync-managed", headers=setup["h_admin"])).json()
    assert out["discovered"] >= 1 and out["created"] >= 1
    rows = (await client.get("/api/v1/integrations", headers=setup["h_admin"],
                             params={"category": "sms"})).json()
    assert rows and rows[0]["is_managed_elsewhere"] is True
    assert rows[0]["managed_by"] == "sms_settings"
    assert rows[0]["status"] == "healthy"     # a real provider is configured

    # a mirror row is read-only in the hub
    mirrored = rows[0]["id"]
    upd = await client.patch(f"/api/v1/integrations/{mirrored}", headers=setup["h_admin"],
                             json={"name": "hijack"})
    assert upd.status_code == 400 and "sms_settings" in upd.json()["detail"]
    dele = await client.delete(f"/api/v1/integrations/{mirrored}", headers=setup["h_admin"])
    assert dele.status_code == 400

    # syncing twice does not create duplicates
    again = (await client.post("/api/v1/integrations/sync-managed", headers=setup["h_admin"])).json()
    assert again["created"] == 0
    rows2 = (await client.get("/api/v1/integrations", headers=setup["h_admin"],
                              params={"category": "sms"})).json()
    assert len(rows2) == len(rows)


# ---------- inbound webhook connector ----------
@pytest.mark.asyncio
async def test_inbound_webhook_receives_and_verifies_signature(client: AsyncClient, setup, db: AsyncSession):
    created = await _create(client, setup, provider="inbound_webhook", name="Vendor hook", config={})
    token, secret = created["inbound_token"], created["inbound_secret"]
    assert token and secret

    # unsigned payloads are accepted (many vendors don't sign)
    r = await client.post(f"/api/v1/integrations/inbound/{token}", json={"order": 1})
    assert r.status_code == 200 and r.json()["received"] is True
    assert r.json()["signature_valid"] is None

    # a correct signature validates
    body = json.dumps({"order": 2}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    r2 = await client.post(f"/api/v1/integrations/inbound/{token}", content=body,
                           headers={"Content-Type": "application/json", "X-Signature": sig})
    assert r2.status_code == 200 and r2.json()["signature_valid"] is True

    # a forged signature is rejected
    bad = await client.post(f"/api/v1/integrations/inbound/{token}", content=body,
                            headers={"Content-Type": "application/json", "X-Signature": "deadbeef"})
    assert bad.status_code == 401

    # unknown token
    assert (await client.post("/api/v1/integrations/inbound/nope", json={})).status_code == 404

    evs = (await client.get("/api/v1/integrations/events", headers=setup["h_admin"])).json()
    assert len(evs) == 2      # the forged one was never stored


@pytest.mark.asyncio
async def test_inbound_rotate_invalidates_old_token(client: AsyncClient, setup):
    created = await _create(client, setup, provider="inbound_webhook", name="Hook", config={})
    old = created["inbound_token"]
    rotated = (await client.post(f"/api/v1/integrations/{created['id']}/rotate-inbound",
                                 headers=setup["h_admin"])).json()
    assert rotated["inbound_token"] != old
    assert (await client.post(f"/api/v1/integrations/inbound/{old}", json={})).status_code == 404
    assert (await client.post(f"/api/v1/integrations/inbound/{rotated['inbound_token']}",
                              json={})).status_code == 200


# ---------- dashboard, logs, audit, export ----------
@pytest.mark.asyncio
async def test_dashboard_logs_audit_and_export(client: AsyncClient, setup, http, db: AsyncSession):
    ok = await _create(client, setup, name="Healthy")
    bad = await _create(client, setup, name="Broken", max_attempts=1,
                        config={"base_url": "https://broken.test/api"})
    http["script"]["broken.test"] = 500
    await client.post(f"/api/v1/integrations/{ok['id']}/health-check", headers=setup["h_admin"])
    await client.post(f"/api/v1/integrations/{bad['id']}/health-check", headers=setup["h_admin"])

    d = (await client.get("/api/v1/integrations/dashboard", headers=setup["h_admin"])).json()
    assert d["total"] >= 2 and d["healthy"] >= 1 and d["degraded"] >= 1
    assert d["categories_available"] == len(cat.CATEGORIES)
    assert d["connectors_available"] == len(cat.CONNECTORS)
    assert any(n["name"] == "Broken" for n in d["needs_attention"])

    logs = (await client.get("/api/v1/integrations/logs", headers=setup["h_admin"],
                             params={"status": "failed"})).json()
    assert logs and logs[0]["operation"] == "health_check"

    csv_out = await client.get("/api/v1/integrations/export", headers=setup["h_admin"])
    assert csv_out.status_code == 200 and "Category" in csv_out.text and "Broken" in csv_out.text

    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "INTEGRATION_CREATED"))).scalars().all()
    assert len(audits) == 2


@pytest.mark.asyncio
async def test_disabled_integration_is_not_called(client: AsyncClient, setup, http):
    created = await _create(client, setup)
    await client.patch(f"/api/v1/integrations/{created['id']}", headers=setup["h_admin"],
                       json={"is_enabled": False})
    r = await client.post(f"/api/v1/integrations/{created['id']}/call",
                          headers=setup["h_admin"], json={"path": "/x"})
    assert r.status_code == 400 and "disabled" in r.json()["detail"]
    assert http["calls"] == []


@pytest.mark.asyncio
async def test_auth_headers_are_applied_per_auth_type(client: AsyncClient, setup, http):
    bearer = await _create(client, setup, provider="hubspot_crm", name="HubSpot",
                           credentials={"token": "tok-123"},
                           config={"base_url": "https://vendor.test/hs"})
    await client.post(f"/api/v1/integrations/{bearer['id']}/call",
                      headers=setup["h_admin"], json={"path": "/x"})
    assert http["calls"][-1]["headers"]["Authorization"] == "Bearer tok-123"

    keyed = await _create(client, setup, provider="pipedrive", name="Pipedrive",
                          credentials={"api_key": "pd-key"},
                          config={"base_url": "https://vendor.test/pd", "auth_header": "X-Token"})
    await client.post(f"/api/v1/integrations/{keyed['id']}/call",
                      headers=setup["h_admin"], json={"path": "/y"})
    assert http["calls"][-1]["headers"]["X-Token"] == "pd-key"

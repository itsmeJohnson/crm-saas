import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
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
    org = await OrganizationRepository(db).create({"name": "Comp Org", "slug": "comp-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@comp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await ur.create_user(org.id, {"email": "mgr@comp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mg", "last_name": "R", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()

    audit = AuditService(db)
    seed = [
        (admin.id, "AUTH_LOGIN", "Auth", {"ip_address": "10.0.0.1", "browser_info": "pytest"}),
        (None, "AUTH_LOGIN_FAILED", "Auth", {"description": "Failed login attempt for email: x@y.com"}),
        (admin.id, "PERMISSION_CHANGED", "custom_role", {"role": "Sales"}),
        (admin.id, "ROLE_UPDATED", "custom_role", None),
        (admin.id, "WORKFLOW_PUBLISHED", "workflow", None),
        (admin.id, "RULE_CREATED", "rule", None),
        (admin.id, "INVOICE_CONFIG_UPDATED", "settings", None),
        (admin.id, "CUSTOMER_INVOICE_CREATED", "invoice", {"amount": 100}),
        (admin.id, "CUSTOMER_PAYMENT_RECORDED", "payment", None),
        (mgr.id, "SMS_SENT", "communication", None),
        (mgr.id, "WHATSAPP_SENT", "communication", None),
        (admin.id, "DATA_EXPORTED", "bi_export", {"kind": "download", "format": "csv"}),
        (admin.id, "BI_FEED_ACCESSED", "bi_token", None),
        (admin.id, "APPROVAL_REQUESTED", "approval", None),
        (mgr.id, "LEAD_ASSIGNED", "lead", None),
    ]
    for actor_id, action, rtype, md in seed:
        await audit.log_event(organization_id=org.id, actor_user_id=actor_id, action=action,
                              resource_type=rtype, action_metadata=md)
    await db.commit()
    return {"org": org, "admin": admin, "mgr": mgr,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"}}


def test_classifier_covers_all_required_categories():
    assert classify("AUTH_LOGIN") == "login"
    assert classify("AUTH_LOGIN_FAILED") == "login"
    assert classify("PERMISSION_CHANGED") == "permission"
    assert classify("FIELD_PERMISSION_CHANGED") == "permission"
    assert classify("USER_CREATED") == "permission"
    assert classify("WORKFLOW_PUBLISHED") == "workflow"
    assert classify("RULE_DELETED") == "workflow"
    assert classify("INVOICE_CONFIG_UPDATED") == "configuration"
    assert classify("COMMERCIAL_SETTINGS_UPDATED") == "configuration"
    assert classify("CUSTOMER_INVOICE_CREATED") == "financial"
    assert classify("PAY_INVOICE_SUCCESS") == "financial"
    assert classify("SMS_SENT") == "communication"
    assert classify("EMAIL_SENT") == "communication"
    assert classify("DATA_EXPORTED") == "export"
    assert classify("BI_FEED_ACCESSED") == "export"
    assert classify("APPROVAL_APPROVED") == "approval"
    assert classify("LEAD_ASSIGNED") == "activity"


@pytest.mark.asyncio
async def test_meta(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/meta", headers=setup["h_admin"])
    keys = [c["key"] for c in r.json()["categories"]]
    for k in ("login", "permission", "workflow", "configuration", "financial",
              "communication", "export", "approval", "activity"):
        assert k in keys


@pytest.mark.asyncio
async def test_logs_with_filters(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"])
    body = r.json()
    assert body["total"] == 15
    assert all("category" in row and "actor_name" in row for row in body["rows"])

    r = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"], params={"category": "financial"})
    assert r.json()["total"] == 2

    r = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"],
                         params={"actor_user_id": str(setup["mgr"].id)})
    assert r.json()["total"] == 3

    r = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"], params={"q": "invoice"})
    assert r.json()["total"] >= 2

    r = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"],
                         params={"limit": 5, "offset": 0})
    assert len(r.json()["rows"]) == 5

    bad = await client.get("/api/v1/compliance/logs", headers=setup["h_admin"], params={"category": "nope"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_login_history(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/login-history", headers=setup["h_admin"])
    rows = r.json()
    assert len(rows) == 2
    ok = next(x for x in rows if x["event"] == "AUTH_LOGIN")
    failed = next(x for x in rows if x["event"] == "AUTH_LOGIN_FAILED")
    assert ok["success"] is True and ok["ip_address"] == "10.0.0.1" and ok["user_name"] == "Ad Min"
    assert failed["success"] is False and "Failed login" in failed["description"]


@pytest.mark.asyncio
async def test_user_activity(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/compliance/user-activity/{setup['mgr'].id}", headers=setup["h_admin"])
    body = r.json()
    assert body["total"] == 3 and body["user_name"] == "Mg R"
    assert body["by_category"]["communication"] == 2 and body["by_category"]["activity"] == 1
    assert any(a["action"] == "SMS_SENT" for a in body["top_actions"])


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["counts"]["last_30d"] == 15
    by_cat = {c["key"]: c["count"] for c in d["by_category"]}
    assert by_cat["login"] == 2 and by_cat["permission"] == 2 and by_cat["export"] == 2
    assert d["failed_logins_30d"] == 1
    assert d["top_actors"][0]["name"] == "Ad Min"
    assert len(d["recent_sensitive"]) >= 3  # permission + configuration + export events


@pytest.mark.asyncio
async def test_compliance_report(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/report", headers=setup["h_admin"], params={"days": 30})
    body = r.json()
    assert body["total_events"] == 15 and body["unique_actors"] == 2 and body["failed_logins"] == 1
    cats = {c["key"]: c for c in body["categories"]}
    assert cats["workflow"]["count"] == 2
    assert any(a["action"] == "WORKFLOW_PUBLISHED" for a in cats["workflow"]["top_actions"])
    assert len(body["permission_changes"]) == 2
    assert len(body["configuration_changes"]) == 1
    assert len(body["data_exports"]) == 2
    assert body["generated_at"] and body["window_start"]


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, setup):
    r = await client.get("/api/v1/compliance/export", headers=setup["h_admin"])
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("created_at,category,action,actor")
    assert len(lines) == 16  # header + 15 events
    r = await client.get("/api/v1/compliance/export", headers=setup["h_admin"], params={"category": "login"})
    assert len(r.text.strip().splitlines()) == 3


@pytest.mark.asyncio
async def test_admin_only(client: AsyncClient, setup):
    for path in ("/api/v1/compliance/logs", "/api/v1/compliance/dashboard",
                 "/api/v1/compliance/report", "/api/v1/compliance/login-history"):
        assert (await client.get(path, headers=setup["h_mgr"])).status_code == 403

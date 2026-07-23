import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.ai_platform import AIPromptTemplate, AIPromptTemplateVersion
from app.models.audit_log import AuditLog
from app.services.prompt_studio_service import detect_variables
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
    org = await OrganizationRepository(db).create({"name": "PS Org", "slug": "ps-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@ps.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@ps.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- pure ----------
def test_detect_variables_dedup_and_order():
    assert detect_variables("Hi {{name}}", "{{ goal }} for {{name}}") == ["name", "goal"]
    assert detect_variables(None, "no vars here") == []


# ---------- library + categories (builtin seeded) ----------
@pytest.mark.asyncio
async def test_library_and_categories(client: AsyncClient, setup):
    lib = (await client.get("/api/v1/prompt-studio/library", headers=setup["h_admin"])).json()
    assert lib["count"] > 0 and all(i["is_builtin"] for i in lib["items"])
    cats = (await client.get("/api/v1/prompt-studio/categories", headers=setup["h_admin"])).json()
    keys = {c["task_type"] for c in cats["categories"]}
    assert "crm" in keys and "general" in keys


# ---------- create → version → approval lifecycle ----------
@pytest.mark.asyncio
async def test_prompt_lifecycle_versioning_and_approval(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/prompt-studio/prompts", headers=setup["h_admin"], json={
        "key": "lead_intro", "name": "Lead intro", "task_type": "crm",
        "system_prompt": "You are a sales assistant.",
        "template": "Write an intro for {{lead_name}} about {{product}}.", "tags": ["sales"]})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "draft" and p["is_active"] is False and p["version"] == 1
    assert p["variables"] == ["lead_name", "product"]  # auto-detected
    pid = p["id"]

    # employees cannot create
    assert (await client.post("/api/v1/prompt-studio/prompts", headers=setup["h_emp"], json={
        "key": "x", "name": "x", "template": "hi"})).status_code == 403

    # edit changes content → snapshots v1, bumps to v2
    r = await client.patch(f"/api/v1/prompt-studio/prompts/{pid}", headers=setup["h_admin"], json={
        "template": "Write a warm intro for {{lead_name}} about {{product}} and {{offer}}.",
        "change_note": "add offer var"})
    assert r.status_code == 200 and r.json()["version"] == 2
    assert "offer" in r.json()["variables"]
    versions = (await client.get(f"/api/v1/prompt-studio/prompts/{pid}/versions", headers=setup["h_admin"])).json()
    assert len(versions) == 1 and versions[0]["version"] == 1 and versions[0]["change_note"] == "add offer var"

    # submit → pending; approve → active + audit
    assert (await client.post(f"/api/v1/prompt-studio/prompts/{pid}/submit", headers=setup["h_admin"])).json()["status"] == "pending_review"
    out = (await client.post(f"/api/v1/prompt-studio/prompts/{pid}/approve", headers=setup["h_admin"], json={})).json()
    assert out["status"] == "approved" and out["is_active"] is True
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id, AuditLog.action == "PROMPT_APPROVED"))).scalars().all()
    assert len(audits) == 1

    # editing an APPROVED prompt sends it back to pending_review (and deactivates)
    r = await client.patch(f"/api/v1/prompt-studio/prompts/{pid}", headers=setup["h_admin"], json={
        "template": "Intro {{lead_name}} / {{product}} / {{offer}} v3.", "change_note": "tweak"})
    assert r.json()["status"] == "pending_review" and r.json()["is_active"] is False and r.json()["version"] == 3

    # restore v1
    r = await client.post(f"/api/v1/prompt-studio/prompts/{pid}/versions/1/restore", headers=setup["h_admin"])
    assert r.status_code == 200 and "{{offer}}" not in r.json()["template"]


# ---------- testing / preview ----------
@pytest.mark.asyncio
async def test_prompt_test_dry_render_and_live_run(client: AsyncClient, setup):
    # inline dry render (no LLM)
    r = await client.post("/api/v1/prompt-studio/test", headers=setup["h_admin"], json={
        "template": "Hello {{name}}, about {{topic}}.", "variables": {"name": "Ada"}})
    assert r.status_code == 200
    body = r.json()
    assert body["rendered_prompt"] == "Hello Ada, about ."
    assert body["declared_variables"] == ["name", "topic"] and body["missing_variables"] == ["topic"]
    assert body["ran"] is False

    # live run through the gateway (mock provider)
    r = await client.post("/api/v1/prompt-studio/test", headers=setup["h_admin"], json={
        "template": "Say hi to {{name}}.", "variables": {"name": "Ada"}, "run": True})
    assert r.status_code == 200
    body = r.json()
    assert body["ran"] is True and body["provider"] == "mock" and body["output"]


# ---------- analytics + export + permissions ----------
@pytest.mark.asyncio
async def test_analytics_export_permissions(client: AsyncClient, setup, db: AsyncSession):
    await client.post("/api/v1/prompt-studio/prompts", headers=setup["h_admin"], json={
        "key": "custom_one", "name": "Custom one", "task_type": "general", "template": "hi {{x}}"})
    an = (await client.get("/api/v1/prompt-studio/analytics", headers=setup["h_admin"])).json()
    assert an["totals"]["prompts"] > 0 and an["totals"]["builtin"] > 0 and an["totals"]["custom"] >= 1
    assert "draft" in an["by_status"]
    assert isinstance(an["top_used"], list)

    # analytics + export are manager-gated
    assert (await client.get("/api/v1/prompt-studio/analytics", headers=setup["h_emp"])).status_code == 403
    assert (await client.get("/api/v1/prompt-studio/export", headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/prompt-studio/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "custom_one" in r.text
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id, AuditLog.action == "PROMPTS_EXPORTED"))).scalars().all()
    assert len(audits) == 1

    # employees CAN read the library/list (all-users) but not analytics
    assert (await client.get("/api/v1/prompt-studio/prompts", headers=setup["h_emp"])).status_code == 200


# ---------- gateway still works: approved Studio prompt is usable ----------
@pytest.mark.asyncio
async def test_approved_prompt_usable_by_gateway(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/prompt-studio/prompts", headers=setup["h_admin"], json={
        "key": "gw_hello", "name": "GW hello", "task_type": "general",
        "template": "Greet {{name}} warmly."})
    pid = r.json()["id"]
    await client.post(f"/api/v1/prompt-studio/prompts/{pid}/submit", headers=setup["h_admin"])
    await client.post(f"/api/v1/prompt-studio/prompts/{pid}/approve", headers=setup["h_admin"], json={})
    # the AI gateway can now render+run it by key
    r = await client.post("/api/v1/ai/generate", headers=setup["h_admin"], json={
        "template_key": "gw_hello", "variables": {"name": "Ada"}})
    assert r.status_code == 200
    assert "Greet Ada warmly" in r.json()["text"]  # mock echoes the rendered prompt

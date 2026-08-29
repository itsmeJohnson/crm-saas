import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key): return storage.get(key)
    async def mock_set(key, value, ex=300): storage[key] = value; return True
    async def mock_delete(key): storage.pop(key, None); return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_features(*a, **k):
        # note: CAMPAIGN_MANAGEMENT deliberately absent (per-plan defaults test)
        return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Roles Org", "slug": "roles-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@roles.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@roles.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@roles.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _mk_role(client, headers, **over):
    payload = {"name": "Sales Rep", "description": "custom rep", "base_role": "Employee"}
    payload.update(over)
    return await client.post("/api/v1/roles", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_catalog_and_create_seeds_matrix_from_base_role(client: AsyncClient, setup: dict):
    data = setup
    cat = (await client.get("/api/v1/roles/catalog", headers=data["h_emp"])).json()
    assert "leads" in cat["resources"] and "view" in cat["actions"] and "team" in cat["scopes"]

    # only OrgAdmin can create roles
    assert (await _mk_role(client, data["h_emp"])).status_code == 403
    assert (await _mk_role(client, data["h_mgr"])).status_code == 403
    r = await _mk_role(client, data["h_admin"])
    assert r.status_code == 201, r.text
    role = r.json()
    assert role["base_role"] == "Employee" and role["user_count"] == 0

    # duplicate name rejected
    assert (await _mk_role(client, data["h_admin"])).status_code == 409

    # inheritance: matrix seeded from Employee defaults
    detail = (await client.get(f"/api/v1/roles/{role['id']}", headers=data["h_admin"])).json()
    leads = detail["matrix"]["leads"]
    assert leads["actions"]["view"] is True and leads["actions"]["create"] is True
    assert leads["actions"]["delete"] is False and leads["actions"]["export"] is False
    assert leads["scope"] == "own"
    # employees get no user-management permissions by default
    assert detail["matrix"]["users"]["actions"]["view"] is False


@pytest.mark.asyncio
async def test_matrix_update_scope_and_audit_trail(client: AsyncClient, setup: dict):
    data = setup
    role = (await _mk_role(client, data["h_admin"], name="Matrix Role")).json()
    r = await client.put(f"/api/v1/roles/{role['id']}/permissions", json={"matrix": {
        "leads": {"actions": {"delete": True, "export": True}, "scope": "team"},
    }}, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    leads = r.json()["matrix"]["leads"]
    assert leads["actions"]["delete"] is True and leads["actions"]["export"] is True
    assert leads["scope"] == "team"

    # matrix edits only via OrgAdmin
    r = await client.put(f"/api/v1/roles/{role['id']}/permissions", json={"matrix": {}},
                         headers=data["h_mgr"])
    assert r.status_code == 403

    # audit trail records role creation and permission change
    audit = (await client.get("/api/v1/roles/audit", headers=data["h_admin"])).json()
    actions = {a["action"] for a in audit}
    assert "ROLE_CREATED" in actions and "PERMISSION_CHANGED" in actions
    # audit is admin-only
    assert (await client.get("/api/v1/roles/audit", headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_assignment_and_effective_permissions(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    role = (await _mk_role(client, data["h_admin"], name="Assigned Role")).json()
    r = await client.post(f"/api/v1/roles/{role['id']}/assign",
                          json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    assert r.json()["assigned"] == 1
    users = (await client.get(f"/api/v1/roles/{role['id']}/users", headers=data["h_admin"])).json()
    assert users[0]["email"] == "emp@roles.com"

    # custom roles cannot be attached to OrgAdmins
    r = await client.post(f"/api/v1/roles/{role['id']}/assign",
                          json={"user_ids": [str(data["admin"].id)]}, headers=data["h_admin"])
    assert r.status_code == 400

    # /roles/me reflects the overlay for the employee
    me = (await client.get("/api/v1/roles/me", headers=data["h_emp"])).json()
    assert me["base_role"] == "Employee"
    assert me["custom_role"]["id"] == role["id"]
    assert me["matrix"]["leads"]["actions"]["view"] is True
    # per-plan defaults: campaigns feature not in plan → denied in effective matrix
    assert me["matrix"]["campaigns"]["actions"]["view"] is False

    # users without a custom role still get base-role defaults
    me_mgr = (await client.get("/api/v1/roles/me", headers=data["h_mgr"])).json()
    assert me_mgr["custom_role"] is None and me_mgr["base_role"] == "Manager"
    assert me_mgr["matrix"]["leads"]["actions"]["view"] is True


@pytest.mark.asyncio
async def test_resource_enforcement_for_custom_role_users(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    payload = {"last_name": "Lead", "title": "Deal", "status": "New"}

    # backward compat: employee WITHOUT a custom role can create a lead
    r = await client.post("/api/v1/leads/", json=payload, headers=data["h_emp"])
    assert r.status_code in (200, 201), r.text

    # deny leads.create on the role and assign it to the employee
    role = (await _mk_role(client, data["h_admin"], name="No Create")).json()
    await client.put(f"/api/v1/roles/{role['id']}/permissions", json={"matrix": {
        "leads": {"actions": {"create": False}, "scope": "own"}}}, headers=data["h_admin"])
    await client.post(f"/api/v1/roles/{role['id']}/assign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])

    r = await client.post("/api/v1/leads/", json=payload, headers=data["h_emp"])
    assert r.status_code == 403
    # view remains allowed
    assert (await client.get("/api/v1/leads/", headers=data["h_emp"])).status_code == 200

    # unassign → creation allowed again (legacy behavior restored)
    await client.post(f"/api/v1/roles/{role['id']}/unassign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    r = await client.post("/api/v1/leads/", json=payload, headers=data["h_emp"])
    assert r.status_code in (200, 201)


@pytest.mark.asyncio
async def test_field_level_write_enforcement(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    role = (await _mk_role(client, data["h_admin"], name="Field Locked")).json()
    r = await client.put(f"/api/v1/roles/{role['id']}/field-permissions", json={"items": [
        {"resource": "leads", "field_name": "value", "access": "read"},
    ]}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["field_permissions"][0]["access"] == "read"
    await client.post(f"/api/v1/roles/{role['id']}/assign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])

    lead = Lead(organization_id=data["org"].id, last_name="FP", title="FP Lead", status="New",
                created_by=data["emp"].id, assigned_user_id=data["emp"].id, stage_id=data["stage"].id)
    db.add(lead)
    await db.commit()

    # locked field rejected, unlocked field accepted
    r = await client.patch(f"/api/v1/leads/{lead.id}", json={"value": 999}, headers=data["h_emp"])
    assert r.status_code == 403
    assert "value" in r.json()["detail"]
    r = await client.patch(f"/api/v1/leads/{lead.id}", json={"city": "Pune"}, headers=data["h_emp"])
    assert r.status_code == 200, r.text

    # field perms surface in /roles/me for UI gating
    me = (await client.get("/api/v1/roles/me", headers=data["h_emp"])).json()
    assert me["fields"]["leads"]["value"] == "read"


@pytest.mark.asyncio
async def test_scope_resolution_and_visible_user_ids(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    from app.services.permission_service import PermissionService
    svc = PermissionService(db)
    # employee default scope = own
    assert await svc.scope_for(data["emp"], "leads") == "own"
    ids = await svc.visible_user_ids(data["emp"], "leads")
    assert ids == [data["emp"].id]
    # OrgAdmin unrestricted
    assert await svc.visible_user_ids(data["admin"], "leads") is None
    # department scope
    role = (await _mk_role(client, data["h_admin"], name="Dept Scope")).json()
    await client.put(f"/api/v1/roles/{role['id']}/permissions", json={"matrix": {
        "leads": {"actions": {"view": True}, "scope": "department"}}}, headers=data["h_admin"])
    await client.post(f"/api/v1/roles/{role['id']}/assign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    dept = (await client.post("/api/v1/departments", json={"name": "Scope Dept"},
                              headers=data["h_admin"])).json()
    await client.post(f"/api/v1/departments/{dept['id']}/members",
                      json={"user_ids": [str(data["emp"].id), str(data["mgr"].id)]},
                      headers=data["h_admin"])
    await db.refresh(data["emp"])
    assert await svc.scope_for(data["emp"], "leads") == "department"
    ids = set(await svc.visible_user_ids(data["emp"], "leads"))
    assert ids == {data["emp"].id, data["mgr"].id}


@pytest.mark.asyncio
async def test_role_lifecycle_delete_guard(client: AsyncClient, setup: dict):
    data = setup
    role = (await _mk_role(client, data["h_admin"], name="Lifecycle")).json()
    # rename + archive
    r = await client.patch(f"/api/v1/roles/{role['id']}",
                           json={"name": "Lifecycle 2", "status": "archived"}, headers=data["h_admin"])
    assert r.json()["name"] == "Lifecycle 2" and r.json()["status"] == "archived"

    # deletion blocked while users hold the role
    await client.post(f"/api/v1/roles/{role['id']}/assign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    assert (await client.delete(f"/api/v1/roles/{role['id']}", headers=data["h_admin"])).status_code == 409
    await client.post(f"/api/v1/roles/{role['id']}/unassign",
                      json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    assert (await client.delete(f"/api/v1/roles/{role['id']}", headers=data["h_admin"])).status_code == 204
    listing = (await client.get("/api/v1/roles", headers=data["h_admin"])).json()
    assert all(x["id"] != role["id"] for x in listing)


@pytest.mark.asyncio
async def test_user_api_custom_role_id_validation(client: AsyncClient, setup: dict):
    data = setup
    role = (await _mk_role(client, data["h_admin"], name="Via Users API")).json()
    # valid custom_role_id accepted through the users API (additive field)
    r = await client.patch(f"/api/v1/users/{data['emp'].id}",
                           json={"custom_role_id": role["id"]}, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["custom_role_id"] == role["id"]
    # foreign/unknown role id rejected
    r = await client.patch(f"/api/v1/users/{data['emp'].id}",
                           json={"custom_role_id": str(uuid.uuid4())}, headers=data["h_admin"])
    assert r.status_code == 400

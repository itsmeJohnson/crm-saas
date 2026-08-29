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
from app.models.activity import Activity
from app.models.task import Task
from app.models.pipeline import PipelineStage
from app.models.department import Department
from app.models.notification import Notification
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
        return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Dept Org", "slug": "dept-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@dept.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@dept.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@dept.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
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


async def _mk(client, headers, **over):
    payload = {"name": "Sales", "code": "SALES", "budget": 10000, "budget_period": "monthly"}
    payload.update(over)
    return await client.post("/api/v1/departments", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_create_permissions_and_code_uniqueness(client: AsyncClient, setup: dict):
    data = setup
    # employee & manager cannot create; only OrgAdmin
    assert (await _mk(client, data["h_emp"])).status_code == 403
    assert (await _mk(client, data["h_mgr"])).status_code == 403
    r = await _mk(client, data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Sales" and r.json()["status"] == "active"
    # duplicate code rejected
    assert (await _mk(client, data["h_admin"], name="Sales 2")).status_code == 409


@pytest.mark.asyncio
async def test_hierarchy_and_cycle_guard(client: AsyncClient, setup: dict):
    data = setup
    parent = (await _mk(client, data["h_admin"], name="Parent", code="P")).json()
    child = (await _mk(client, data["h_admin"], name="Child", code="C",
                       parent_department_id=parent["id"])).json()
    assert child["parent_department_id"] == parent["id"]

    # making the parent a child of its own child = cycle → 400
    r = await client.patch(f"/api/v1/departments/{parent['id']}",
                           json={"parent_department_id": child["id"]}, headers=data["h_admin"])
    assert r.status_code == 400

    # self-parent rejected
    r = await client.patch(f"/api/v1/departments/{parent['id']}",
                           json={"parent_department_id": parent["id"]}, headers=data["h_admin"])
    assert r.status_code == 400

    # tree reflects the hierarchy
    tree = await client.get("/api/v1/departments/tree", headers=data["h_admin"])
    root = next(n for n in tree.json() if n["id"] == parent["id"])
    assert any(c["id"] == child["id"] for c in root["children"])


@pytest.mark.asyncio
async def test_head_and_members_assignment(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    dept = (await _mk(client, data["h_admin"], head_user_id=str(data["mgr"].id))).json()
    assert dept["head_user_id"] == str(data["mgr"].id)
    assert dept["head_name"] == "Mgr One"

    # assign members (emp) → notifies head
    r = await client.post(f"/api/v1/departments/{dept['id']}/members",
                          json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    assert r.json()["assigned"] == 1

    await db.refresh(data["emp"])
    assert data["emp"].department_id == uuid.UUID(dept["id"])

    members = await client.get(f"/api/v1/departments/{dept['id']}/members", headers=data["h_admin"])
    assert any(m["id"] == str(data["emp"].id) for m in members.json())

    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "department"))).scalars().first()
    assert notif is not None

    # member count reflected
    got = await client.get(f"/api/v1/departments/{dept['id']}", headers=data["h_admin"])
    assert got.json()["member_count"] == 1

    # remove member
    r = await client.post(f"/api/v1/departments/{dept['id']}/members/remove",
                          json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    assert r.json()["removed"] == 1
    await db.refresh(data["emp"])
    assert data["emp"].department_id is None


@pytest.mark.asyncio
async def test_targets_and_performance_rollup(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    dept = (await _mk(client, data["h_admin"])).json()
    # emp is a member with a converted lead + a call + a done task
    await client.post(f"/api/v1/departments/{dept['id']}/members", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    lead = Lead(organization_id=data["org"].id, first_name="C", last_name="L", title="L", status="Won", value=2000,
                assigned_user_id=data["emp"].id, created_by=data["admin"].id, stage_id=data["stage"].id)
    call = Activity(organization_id=data["org"].id, activity_type="Call", subject="c", status="Completed",
                    assigned_user_id=data["emp"].id, created_by=data["emp"].id)
    task = Task(organization_id=data["org"].id, title="t", status="Done", assigned_user_id=data["emp"].id, created_by=data["admin"].id)
    db.add_all([lead, call, task])
    await db.commit()

    # a KPI target on leads_converted
    r = await client.post(f"/api/v1/departments/{dept['id']}/targets", json={
        "name": "Conversions", "metric": "leads_converted", "target_value": 4, "period": "monthly"}, headers=data["h_admin"])
    assert r.status_code == 201, r.text

    perf = await client.get(f"/api/v1/departments/{dept['id']}/performance", headers=data["h_admin"])
    p = perf.json()
    assert p["member_count"] == 1
    assert p["metrics"]["leads_converted"] == 1
    assert p["metrics"]["calls_made"] == 1
    assert p["metrics"]["tasks_completed"] == 1
    assert p["metrics"]["revenue"] == 2000.0
    kpi = p["kpis"][0]
    assert kpi["metric"] == "leads_converted" and kpi["actual"] == 1 and kpi["attainment"] == 25.0


@pytest.mark.asyncio
async def test_status_and_delete_guard(client: AsyncClient, setup: dict):
    data = setup
    dept = (await _mk(client, data["h_admin"])).json()
    # archive
    r = await client.post(f"/api/v1/departments/{dept['id']}/status", json={"status": "archived"}, headers=data["h_admin"])
    assert r.json()["status"] == "archived"

    # add a member, then deletion is blocked
    await client.post(f"/api/v1/departments/{dept['id']}/members", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    r = await client.delete(f"/api/v1/departments/{dept['id']}", headers=data["h_admin"])
    assert r.status_code == 409

    # remove member, then delete succeeds
    await client.post(f"/api/v1/departments/{dept['id']}/members/remove", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    r = await client.delete(f"/api/v1/departments/{dept['id']}", headers=data["h_admin"])
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_search_filter_and_dashboard(client: AsyncClient, setup: dict):
    data = setup
    await _mk(client, data["h_admin"], name="Sales", code="S1")
    await _mk(client, data["h_admin"], name="Marketing", code="M1")
    arch = (await _mk(client, data["h_admin"], name="Legacy", code="L1")).json()
    await client.post(f"/api/v1/departments/{arch['id']}/status", json={"status": "archived"}, headers=data["h_admin"])

    r = await client.get("/api/v1/departments", params={"search": "Market"}, headers=data["h_admin"])
    assert r.json()["total"] == 1 and r.json()["items"][0]["name"] == "Marketing"
    r = await client.get("/api/v1/departments", params={"status": "archived"}, headers=data["h_admin"])
    assert r.json()["total"] == 1

    d = await client.get("/api/v1/departments/dashboard", headers=data["h_admin"])
    assert d.json()["total"] == 3 and d.json()["active"] == 2 and d.json()["archived"] == 1


@pytest.mark.asyncio
async def test_export_import_csv(client: AsyncClient, setup: dict):
    data = setup
    await _mk(client, data["h_admin"], name="Sales", code="SL")
    # export
    r = await client.get("/api/v1/departments/export", headers=data["h_admin"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "name,code,description" in r.text

    # import (one new, plus a header)
    csv_bytes = b"name,code,description,budget,status\nSupport,SUP,Helpdesk,5000,active\n"
    files = {"file": ("dept.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/departments/import", files=files, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["created"] == 1
    r = await client.get("/api/v1/departments", params={"search": "Support"}, headers=data["h_admin"])
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_user_department_integration_backward_compat(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    dept = (await _mk(client, data["h_admin"])).json()

    # creating a user WITHOUT department_id still works (backward compatible)
    r = await client.post("/api/v1/users/", json={
        "email": "new@dept.com", "first_name": "New", "last_name": "User", "role": "Employee",
        "reporting_to_id": str(data["mgr"].id), "password": "password123"}, headers=data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json().get("department_id") is None

    # assigning via the user update path validates + persists department_id
    new_id = r.json()["id"]
    r = await client.patch(f"/api/v1/users/{new_id}", json={"department_id": dept["id"]}, headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["department_id"] == dept["id"]

    # a bogus department is rejected
    r = await client.patch(f"/api/v1/users/{new_id}", json={"department_id": str(uuid.uuid4())}, headers=data["h_admin"])
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_analytics(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    dept = (await _mk(client, data["h_admin"])).json()
    await client.post(f"/api/v1/departments/{dept['id']}/members", json={"user_ids": [str(data["emp"].id)]}, headers=data["h_admin"])
    lead = Lead(organization_id=data["org"].id, first_name="C", last_name="L", title="L", status="Won", value=3000,
                assigned_user_id=data["emp"].id, created_by=data["admin"].id, stage_id=data["stage"].id)
    db.add(lead)
    await db.commit()
    r = await client.get("/api/v1/departments/analytics", headers=data["h_admin"])
    row = next(x for x in r.json() if x["department_id"] == dept["id"])
    assert row["revenue"] == 3000.0 and row["leads_converted"] == 1 and row["member_count"] == 1

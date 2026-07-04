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
        return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "BT Org", "slug": "bt-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@bt.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@bt.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@bt.com", "hashed_password": get_password_hash("password123"),
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


async def _mk_territory(client, headers, **over):
    payload = {"name": "West Region", "code": "WEST", "level": "region"}
    payload.update(over)
    return await client.post("/api/v1/territories", json=payload, headers=headers)


async def _mk_branch(client, headers, **over):
    payload = {"name": "Mumbai Branch", "code": "MUM", "city": "Mumbai"}
    payload.update(over)
    return await client.post("/api/v1/branches", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_territory_permissions_hierarchy_and_cycle_guard(client: AsyncClient, setup: dict):
    data = setup
    # only OrgAdmin can create
    assert (await _mk_territory(client, data["h_emp"])).status_code == 403
    assert (await _mk_territory(client, data["h_mgr"])).status_code == 403
    region = (await _mk_territory(client, data["h_admin"])).json()
    assert region["level"] == "region"
    # duplicate code rejected
    assert (await _mk_territory(client, data["h_admin"], name="West 2")).status_code == 409
    # invalid level rejected
    assert (await _mk_territory(client, data["h_admin"], name="Bad", code="BAD", level="planet")).status_code == 422

    zone = (await _mk_territory(client, data["h_admin"], name="Mum Zone", code="MZ",
                                level="zone", parent_id=region["id"])).json()
    assert zone["parent_id"] == region["id"]
    # cycle: make region a child of its own child
    r = await client.patch(f"/api/v1/territories/{region['id']}",
                           json={"parent_id": zone["id"]}, headers=data["h_admin"])
    assert r.status_code == 400
    # tree shows hierarchy
    tree = (await client.get("/api/v1/territories/tree", headers=data["h_admin"])).json()
    root = next(n for n in tree if n["id"] == region["id"])
    assert any(c["id"] == zone["id"] for c in root["children"])


@pytest.mark.asyncio
async def test_branch_crud_manager_notify_and_uniqueness(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    r = await _mk_branch(client, data["h_admin"], territory_id=region["id"],
                         branch_manager_id=str(data["mgr"].id), is_head_office=True)
    assert r.status_code == 201, r.text
    branch = r.json()
    assert branch["manager_name"] == "Mgr One" and branch["territory_name"] == "West Region"
    assert branch["is_head_office"] is True
    # branch manager notified
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "branch"))).scalars().first()
    assert notif is not None
    # duplicate code rejected; employee cannot create
    assert (await _mk_branch(client, data["h_admin"], name="Mum 2")).status_code == 409
    assert (await _mk_branch(client, data["h_emp"], name="X", code="X")).status_code == 403
    # multiple branches supported + list filter by city
    await _mk_branch(client, data["h_admin"], name="Pune Branch", code="PUN", city="Pune")
    lst = (await client.get("/api/v1/branches", params={"city": "Pune"}, headers=data["h_admin"])).json()
    assert lst["total"] == 1 and lst["items"][0]["name"] == "Pune Branch"


@pytest.mark.asyncio
async def test_pincode_mapping_crud_and_import(client: AsyncClient, setup: dict):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"])).json()
    # upsert a mapping
    r = await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "city": "Mumbai", "territory_id": region["id"], "branch_id": branch["id"],
    }, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["pin_code"] == "400001"
    # upsert same pin updates in place (still one row)
    await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "city": "Mumbai City", "territory_id": region["id"]}, headers=data["h_admin"])
    lst = (await client.get("/api/v1/branches/pincodes", headers=data["h_admin"])).json()
    assert lst["total"] == 1
    # CSV import by code
    csv_content = ("pin_code,city,territory_code,branch_code\n"
                   "411001,Pune,WEST,MUM\n"
                   "500001,Hyderabad,NOPE,\n")
    r = await client.post("/api/v1/branches/pincodes/import",
                          files={"file": ("pins.csv", csv_content, "text/csv")}, headers=data["h_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and len(body["errors"]) == 1  # NOPE territory missing
    # employee cannot mutate
    assert (await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "999999", "territory_id": region["id"]}, headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_lead_auto_territory_on_create_and_by_city(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"])).json()
    await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "city": "Mumbai", "territory_id": region["id"], "branch_id": branch["id"],
    }, headers=data["h_admin"])

    # lead with a mapped PIN auto-resolves branch+territory
    r = await client.post("/api/v1/leads/", json={
        "last_name": "Pinned", "title": "Deal", "pin_code": "400001"}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text
    lead = r.json()
    assert lead["branch_id"] == branch["id"] and lead["territory_id"] == region["id"]

    # lead with only a city that a branch sits in resolves via city fallback
    r = await client.post("/api/v1/leads/", json={
        "last_name": "CityOnly", "title": "Deal2", "city": "Mumbai"}, headers=data["h_admin"])
    lead2 = r.json()
    assert lead2["territory_id"] == region["id"]

    # unmapped lead stays NULL (backward compatible)
    r = await client.post("/api/v1/leads/", json={
        "last_name": "Nowhere", "title": "Deal3", "pin_code": "000000"}, headers=data["h_admin"])
    assert r.json()["branch_id"] is None and r.json()["territory_id"] is None


@pytest.mark.asyncio
async def test_explicit_and_auto_lead_assignment_endpoint(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"],
                               branch_manager_id=str(data["mgr"].id))).json()
    await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "territory_id": region["id"], "branch_id": branch["id"]}, headers=data["h_admin"])

    # two leads created without mapping (no pin) so they stay unassigned
    l1 = Lead(organization_id=data["org"].id, last_name="A", title="A", status="New",
              created_by=data["admin"].id, stage_id=data["stage"].id, pin_code="400001")
    l2 = Lead(organization_id=data["org"].id, last_name="B", title="B", status="New",
              created_by=data["admin"].id, stage_id=data["stage"].id)  # no pin/city
    db.add(l1); db.add(l2)
    await db.commit()

    # explicit assignment
    r = await client.post("/api/v1/branches/assign-leads", json={
        "lead_ids": [str(l2.id)], "branch_id": branch["id"], "territory_id": region["id"]}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["assigned"] == 1
    await db.refresh(l2)
    assert l2.branch_id == uuid.UUID(branch["id"])

    # auto assignment resolves l1 by its pin, l-unresolved stays counted
    l3 = Lead(organization_id=data["org"].id, last_name="C", title="C", status="New",
              created_by=data["admin"].id, stage_id=data["stage"].id)  # unresolvable
    db.add(l3); await db.commit()
    r = await client.post("/api/v1/branches/assign-leads", json={
        "lead_ids": [str(l1.id), str(l3.id)], "auto": True}, headers=data["h_admin"])
    body = r.json()
    assert body["assigned"] == 1 and body["unresolved"] == 1
    await db.refresh(l1)
    assert l1.territory_id == uuid.UUID(region["id"])
    # branch manager notified of inflow
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "branch",
        Notification.title == "Leads routed to your branch"))).scalars().first()
    assert notif is not None


@pytest.mark.asyncio
async def test_dashboard_performance_reports_and_locations(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    (await _mk_territory(client, data["h_admin"], name="Mumbai", code="C-MUM", level="city"))
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"])).json()
    bid = uuid.UUID(branch["id"]); rid = uuid.UUID(region["id"])
    # leads flowing to the branch: one won w/ revenue, one open
    db.add(Lead(organization_id=data["org"].id, last_name="Won", title="W", status="Won", value=1000,
                created_by=data["admin"].id, stage_id=data["stage"].id, branch_id=bid, territory_id=rid))
    db.add(Lead(organization_id=data["org"].id, last_name="Open", title="O", status="New",
                created_by=data["admin"].id, stage_id=data["stage"].id, branch_id=bid, territory_id=rid))
    await db.commit()

    perf = (await client.get(f"/api/v1/branches/{branch['id']}/performance", headers=data["h_admin"])).json()
    assert perf["metrics"]["leads"] == 2 and perf["metrics"]["converted"] == 1
    assert perf["metrics"]["revenue"] == 1000.0 and perf["metrics"]["conversion_rate"] == 50.0

    dash = (await client.get("/api/v1/branches/dashboard", headers=data["h_admin"])).json()
    assert dash["total_branches"] == 1 and dash["total_territories"] == 2
    assert dash["top_branches"][0]["lead_count"] == 2

    rows = (await client.get("/api/v1/branches/analytics", headers=data["h_admin"])).json()
    assert rows[0]["revenue"] == 1000.0
    trows = (await client.get("/api/v1/territories/analytics", headers=data["h_admin"])).json()
    assert any(t["territory_id"] == region["id"] and t["leads"] == 2 for t in trows)

    # location filters expose regions + cities; employees can view (read-only)
    locs = (await client.get("/api/v1/territories/locations", headers=data["h_emp"])).json()
    assert any(x["name"] == "West Region" for x in locs["regions"])
    assert any(x["name"] == "Mumbai" for x in locs["cities"])

    # branch export CSV
    r = await client.get("/api/v1/branches/export", headers=data["h_admin"])
    assert r.status_code == 200 and "Mumbai Branch" in r.text


@pytest.mark.asyncio
async def test_delete_guards(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"])).json()
    await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "territory_id": region["id"], "branch_id": branch["id"]}, headers=data["h_admin"])

    # territory delete blocked by branch + pincode references
    assert (await client.delete(f"/api/v1/territories/{region['id']}", headers=data["h_admin"])).status_code == 409

    # branch delete blocked while leads reference it
    db.add(Lead(organization_id=data["org"].id, last_name="L", title="L", status="New",
                created_by=data["admin"].id, stage_id=data["stage"].id, branch_id=uuid.UUID(branch["id"])))
    await db.commit()
    assert (await client.delete(f"/api/v1/branches/{branch['id']}", headers=data["h_admin"])).status_code == 409


@pytest.mark.asyncio
async def test_workflow_assign_territory_action(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    region = (await _mk_territory(client, data["h_admin"])).json()
    branch = (await _mk_branch(client, data["h_admin"], territory_id=region["id"])).json()
    await client.post("/api/v1/branches/pincodes", json={
        "pin_code": "400001", "territory_id": region["id"], "branch_id": branch["id"]}, headers=data["h_admin"])

    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Territory router", "trigger_event": "lead_created", "conditions": [],
        "actions": [{"type": "assign_territory"}],
    }, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text

    from app.services.workflow_service import WorkflowService
    lead = Lead(organization_id=data["org"].id, last_name="Wf", title="WF", status="New",
                created_by=data["admin"].id, stage_id=data["stage"].id, pin_code="400001")
    db.add(lead); await db.commit()
    applied = await WorkflowService(db).run("lead_created", lead, data["admin"])
    await db.commit()
    assert "assign_territory" in applied
    assert lead.territory_id == uuid.UUID(region["id"])
    assert lead.branch_id == uuid.UUID(branch["id"])

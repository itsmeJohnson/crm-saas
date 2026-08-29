import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.workflow import Workflow, WorkflowExecution, WorkflowExecutionStep
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
    org = await org_repo.create({"name": "WF Org", "slug": "wf-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@wf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@wf.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "emp": emp, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


def _graph(actions):
    nodes = [{"id": "t1", "type": "trigger", "config": {"conditions": []}}]
    edges = []
    prev = "t1"
    for i, a in enumerate(actions):
        nid = f"a{i}"
        nodes.append({"id": nid, "type": "action", "config": a})
        edges.append({"from": prev, "to": nid})
        prev = nid
    nodes.append({"id": "end", "type": "end", "config": {}})
    edges.append({"from": prev, "to": "end"})
    return {"nodes": nodes, "edges": edges}


@pytest.mark.asyncio
async def test_catalog_crud_permissions_and_publish_lifecycle(client: AsyncClient, setup: dict):
    data = setup
    cat = (await client.get("/api/v1/workflows/catalog", headers=data["h_admin"])).json()
    assert "lead_created" in [t["event"] for t in cat["triggers"]]
    assert "assign_lead" in cat["actions"] and "branch" in cat["node_types"]
    # employee cannot create
    assert (await client.post("/api/v1/workflows", json={"name": "x", "trigger_event": "lead_created"}, headers=data["h_emp"])).status_code == 403
    # invalid trigger rejected
    assert (await client.post("/api/v1/workflows", json={"name": "x", "trigger_event": "teleport"}, headers=data["h_admin"])).status_code == 400
    # create draft
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Lead flow", "category": "Sales", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Contacted"}])}, headers=data["h_admin"])).json()
    assert wf["status"] == "draft" and wf["version"] == 1 and wf["node_count"] == 3
    # publish → published + a version snapshot
    pub = (await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={"notes": "v1"}, headers=data["h_admin"])).json()
    assert pub["status"] == "published"
    versions = (await client.get(f"/api/v1/workflows/{wf['id']}/versions", headers=data["h_admin"])).json()
    assert versions[0]["version"] == 1
    # editing a published workflow drops it back to draft
    upd = (await client.patch(f"/api/v1/workflows/{wf['id']}", json={
        "graph": _graph([{"action": "update_status", "value": "Qualified"}])}, headers=data["h_admin"])).json()
    assert upd["status"] == "draft"


@pytest.mark.asyncio
async def test_dispatch_runs_published_workflow_on_trigger(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # a published, enabled workflow: on lead_created → set status Contacted + notify
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Auto contact", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Contacted"},
                         {"action": "create_notification", "title": "New lead", "user_id": str(data["admin"].id)}])},
        headers=data["h_admin"])).json()
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])
    # create a lead → triggers the orchestration engine via the legacy run() hook
    r = await client.post("/api/v1/leads/", json={"last_name": "Auto", "title": "Deal"}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text
    lead = r.json()
    # workflow mutated the lead status
    assert lead["status"] == "Contacted"
    # an execution + steps were recorded
    ex = (await db.execute(select(WorkflowExecution).filter(
        WorkflowExecution.workflow_id == uuid.UUID(wf["id"]), WorkflowExecution.is_test == False))).scalars().first()
    assert ex is not None and ex.status == "completed" and ex.steps_run == 2
    steps = (await client.get(f"/api/v1/workflows/executions/{ex.id}", headers=data["h_admin"])).json()
    assert any(s["action_type"] == "update_status" for s in steps["steps"])

    # a DRAFT workflow must NOT run
    draft = (await client.post("/api/v1/workflows", json={
        "name": "Draft flow", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Won"}])}, headers=data["h_admin"])).json()
    r2 = await client.post("/api/v1/leads/", json={"last_name": "Two", "title": "D2"}, headers=data["h_admin"])
    assert r2.json()["status"] == "Contacted"  # from the published one, not the draft's "Won"


@pytest.mark.asyncio
async def test_branch_and_test_run(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # branch: value >= 1000 → update_status; else straight to end
    graph = {"nodes": [
        {"id": "t1", "type": "trigger", "config": {"conditions": []}},
        {"id": "b1", "type": "branch", "config": {"conditions": [{"field": "value", "op": "gte", "value": 1000}]}},
        {"id": "a1", "type": "action", "config": {"action": "update_status", "value": "Hot"}},
        {"id": "end", "type": "end", "config": {}},
    ], "edges": [{"from": "t1", "to": "b1"}, {"from": "b1", "to": "a1", "branch": "true"},
                 {"from": "b1", "to": "end", "branch": "false"}, {"from": "a1", "to": "end"}]}
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Branch flow", "trigger_event": "lead_updated", "graph": graph}, headers=data["h_admin"])).json()
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])

    # a low-value lead update → branch false → status unchanged
    low = Lead(organization_id=data["org"].id, last_name="Low", title="L", status="New", value=100,
               created_by=data["admin"].id, stage_id=data["stage"].id)
    db.add(low); await db.commit()
    await client.patch(f"/api/v1/leads/{low.id}", json={"priority": "High"}, headers=data["h_admin"])
    await db.refresh(low)
    assert low.status == "New"
    # a high-value lead update → branch true → status Hot
    high = Lead(organization_id=data["org"].id, last_name="High", title="H", status="New", value=5000,
                created_by=data["admin"].id, stage_id=data["stage"].id)
    db.add(high); await db.commit()
    await client.patch(f"/api/v1/leads/{high.id}", json={"priority": "High"}, headers=data["h_admin"])
    await db.refresh(high)
    assert high.status == "Hot"

    # TEST MODE: dry run mutates nothing but records a test execution
    test_ex = (await client.post(f"/api/v1/workflows/{wf['id']}/test", json={}, headers=data["h_admin"])).json()
    assert test_ex["is_test"] is True and test_ex["status"] == "test"
    assert any("[test]" in (s.get("detail") or "") for s in test_ex["steps"])


@pytest.mark.asyncio
async def test_clone_export_import_templates_rollback(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Base", "category": "Sales", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Contacted"}])}, headers=data["h_admin"])).json()
    # clone
    cl = (await client.post(f"/api/v1/workflows/{wf['id']}/clone", headers=data["h_admin"])).json()
    assert cl["name"].endswith("(copy)") and cl["status"] == "draft"
    # export → import round-trip
    exported = (await client.get(f"/api/v1/workflows/{wf['id']}/export", headers=data["h_admin"])).json()
    assert exported["_format"] == "crm.workflow.v1"
    imp = (await client.post("/api/v1/workflows/import", json=exported, headers=data["h_admin"])).json()
    assert imp["trigger_event"] == "lead_created"
    # templates: seed built-ins + instantiate
    seeded = (await client.post("/api/v1/workflows/templates/seed", json={}, headers=data["h_admin"])).json()
    assert seeded["created"] >= 1
    tpls = (await client.get("/api/v1/workflows", params={"is_template": True}, headers=data["h_admin"])).json()
    inst = (await client.post(f"/api/v1/workflows/templates/{tpls[0]['id']}/instantiate", headers=data["h_admin"])).json()
    assert inst["is_template"] is False
    # rollback: publish v1, edit + publish v2, then restore v1
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])
    await client.patch(f"/api/v1/workflows/{wf['id']}", json={
        "graph": _graph([{"action": "update_status", "value": "Won"}])}, headers=data["h_admin"])
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])
    rb = (await client.post(f"/api/v1/workflows/{wf['id']}/rollback", json={"version": 1}, headers=data["h_admin"])).json()
    detail = (await client.get(f"/api/v1/workflows/{rb['id']}", headers=data["h_admin"])).json()
    vals = [n["config"].get("value") for n in detail["graph"]["nodes"] if n["type"] == "action"]
    assert "Contacted" in vals  # restored v1's action


@pytest.mark.asyncio
async def test_execution_rollback_and_report(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Statuser", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Contacted"}])}, headers=data["h_admin"])).json()
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])
    lead = (await client.post("/api/v1/leads/", json={"last_name": "Rb", "title": "Deal"}, headers=data["h_admin"])).json()
    assert lead["status"] == "Contacted"
    ex = (await db.execute(select(WorkflowExecution).filter(
        WorkflowExecution.workflow_id == uuid.UUID(wf["id"]), WorkflowExecution.is_test == False))).scalars().first()
    # roll the execution back → lead status restored to its prior value (New)
    r = await client.post(f"/api/v1/workflows/executions/{ex.id}/rollback", headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["reverted"] == 1
    lead2 = (await client.get(f"/api/v1/leads/{lead['id']}", headers=data["h_admin"])).json()
    assert lead2["status"] == "New"
    # cannot roll back twice
    assert (await client.post(f"/api/v1/workflows/executions/{ex.id}/rollback", headers=data["h_admin"])).status_code == 409

    # report + dashboard
    rep = (await client.get("/api/v1/workflows/report", headers=data["h_admin"])).json()
    assert rep["published"] >= 1 and rep["total_runs"] >= 1
    dash = (await client.get("/api/v1/workflows/dashboard", headers=data["h_admin"])).json()
    assert "success_rate" in dash and "recent" in dash


@pytest.mark.asyncio
async def test_enable_disable_and_legacy_backward_compat(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    wf = (await client.post("/api/v1/workflows", json={
        "name": "Toggle", "trigger_event": "lead_created",
        "graph": _graph([{"action": "update_status", "value": "Contacted"}])}, headers=data["h_admin"])).json()
    await client.post(f"/api/v1/workflows/{wf['id']}/publish", json={}, headers=data["h_admin"])
    # disable → workflow does NOT run
    await client.post(f"/api/v1/workflows/{wf['id']}/enable", json={"enabled": False}, headers=data["h_admin"])
    lead = (await client.post("/api/v1/leads/", json={"last_name": "Off", "title": "D"}, headers=data["h_admin"])).json()
    assert lead["status"] == "New"

    # backward compatibility: the LEGACY rule engine still works alongside
    legacy = await client.post("/api/v1/leads/workflows", json={
        "name": "Legacy rule", "trigger_event": "lead_created", "conditions": [],
        "actions": [{"type": "set_priority", "value": "Urgent"}]}, headers=data["h_admin"])
    assert legacy.status_code in (200, 201), legacy.text
    lead2 = (await client.post("/api/v1/leads/", json={"last_name": "Legacy", "title": "D"}, headers=data["h_admin"])).json()
    assert lead2["priority"] == "Urgent"  # legacy rule fired

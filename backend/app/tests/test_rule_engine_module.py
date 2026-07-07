import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.rule import Rule, RuleEvaluation
from app.services import rule_evaluator as ev
from app.core.redis import redis_client


# ---------------- pure evaluator unit tests (no DB) ----------------
def test_evaluator_and_or_not():
    d = {"type": "group", "logic": "and", "children": [
        {"type": "condition", "field": "value", "op": "gte", "value": 1000},
        {"type": "group", "logic": "or", "children": [
            {"type": "condition", "field": "status", "op": "eq", "value": "New"},
            {"type": "condition", "field": "status", "op": "eq", "value": "Contacted"}]},
        {"type": "group", "logic": "not", "children": [
            {"type": "condition", "field": "source", "op": "in", "value": "Spam,Junk"}]},
    ]}
    assert ev.evaluate(d, {"value": 5000, "status": "New", "source": "Website"}) is True
    assert ev.evaluate(d, {"value": 500, "status": "New", "source": "Website"}) is False   # value fails
    assert ev.evaluate(d, {"value": 5000, "status": "Lost", "source": "Website"}) is False  # OR fails
    assert ev.evaluate(d, {"value": 5000, "status": "New", "source": "Spam"}) is False      # NOT fails


def test_evaluator_operators():
    f = {"name": "Acme Corp", "email": "a@b.com", "tags": None, "score": 55}
    assert ev.evaluate([{"field": "name", "op": "starts_with", "value": "Acme"}], f)
    assert ev.evaluate([{"field": "name", "op": "ends_with", "value": "Corp"}], f)
    assert ev.evaluate([{"field": "email", "op": "regex", "value": r"^\w+@\w+\.\w+$"}], f)
    assert ev.evaluate([{"field": "tags", "op": "is_empty"}], f)
    assert ev.evaluate([{"field": "score", "op": "between", "value": "50,60"}], f)
    assert not ev.evaluate([{"field": "score", "op": "between", "value": "10,20"}], f)


def test_evaluator_date_time_and_variables():
    now = datetime(2026, 7, 5, 14, 30)
    ctx = {"now": now}
    assert ev.evaluate([{"field": "d", "op": "date_within_last_days", "value": 7}], {"d": "2026-07-01"}, ctx)
    assert ev.evaluate([{"field": "d", "op": "date_older_than_days", "value": 30}], {"d": "2026-01-01"}, ctx)
    assert ev.evaluate([{"field": "t", "op": "time_after", "value": "09:00"}], {"t": "14:30"})
    assert ev.evaluate([{"field": "t", "op": "time_between", "value": "22:00,06:00"}], {"t": "23:30"})  # overnight
    # dynamic variable: created today == variable today
    assert ev.evaluate([{"field": "d", "op": "date_on", "value_type": "variable", "variable": "today"}],
                       {"d": "2026-07-05"}, ctx)


def test_evaluator_field_to_field():
    assert ev.evaluate([{"field": "a", "op": "gt", "value_type": "field", "value_field": "b"}], {"a": 10, "b": 5})
    assert not ev.evaluate([{"field": "a", "op": "gt", "value_type": "field", "value_field": "b"}], {"a": 3, "b": 5})


# ---------------- API / service integration ----------------
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
    org = await OrganizationRepository(db).create({"name": "Rule Org", "slug": "rule-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@rule.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@rule.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def _hot_lead_def():
    return {"type": "group", "logic": "and", "children": [
        {"type": "condition", "field": "value", "op": "gte", "value": 50000},
        {"type": "group", "logic": "or", "children": [
            {"type": "condition", "field": "status", "op": "eq", "value": "New"},
            {"type": "condition", "field": "status", "op": "eq", "value": "Contacted"}]},
    ]}


@pytest.mark.asyncio
async def test_catalog_crud_permissions_validation(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/rules/catalog", headers=d["h_admin"])).json()
    assert "lead" in cat["entity_types"] and "in" in cat["operators"]["comparison"]
    assert "date_within_last_days" in cat["operators"]["date"] and "today" in cat["variables"]
    # employee cannot create
    assert (await client.post("/api/v1/rules", json={"name": "x", "entity_type": "lead"}, headers=d["h_emp"])).status_code == 403
    # invalid field rejected
    bad = await client.post("/api/v1/rules", json={"name": "bad", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "not_a_field", "op": "eq", "value": 1}]}}, headers=d["h_admin"])
    assert bad.status_code == 400
    # invalid operator rejected
    badop = await client.post("/api/v1/rules", json={"name": "bad", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "status", "op": "no_such_op", "value": 1}]}}, headers=d["h_admin"])
    assert badop.status_code == 400
    # valid create
    r = (await client.post("/api/v1/rules", json={"name": "Hot lead", "category": "Lead Scoring",
        "entity_type": "lead", "priority": 200, "definition": _hot_lead_def()}, headers=d["h_admin"])).json()
    assert r["condition_count"] == 3 and r["priority"] == 200 and r["is_active"] is True


@pytest.mark.asyncio
async def test_test_endpoint_sample_and_live_entity(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    r = (await client.post("/api/v1/rules", json={"name": "Hot lead", "entity_type": "lead",
        "definition": _hot_lead_def()}, headers=d["h_admin"])).json()
    # sample that matches
    res = (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"value": 60000, "status": "New"}}, headers=d["h_admin"])).json()
    assert res["matched"] is True and res["trace"]["matched"] is True
    # sample that fails
    res2 = (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"value": 100, "status": "New"}}, headers=d["h_admin"])).json()
    assert res2["matched"] is False
    # against a live lead entity
    lead = Lead(organization_id=d["org"].id, last_name="Big", title="Deal", status="Contacted", value=75000,
                created_by=d["admin"].id, stage_id=d["stage"].id)
    db.add(lead); await db.commit()
    res3 = (await client.post(f"/api/v1/rules/{r['id']}/test", json={"entity_id": str(lead.id)}, headers=d["h_admin"])).json()
    assert res3["matched"] is True
    # a test evaluation was recorded
    n = (await db.execute(select(RuleEvaluation).filter(RuleEvaluation.rule_id == uuid.UUID(r["id"])))).scalars().all()
    assert len(n) >= 3 and all(e.is_test for e in n)


@pytest.mark.asyncio
async def test_priority_ordering_and_conflict_resolution(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # two matching rules with different priorities
    low = (await client.post("/api/v1/rules", json={"name": "Any lead", "entity_type": "lead", "priority": 50,
        "conflict_strategy": "highest_priority",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "status", "op": "is_not_empty"}]}}, headers=d["h_admin"])).json()
    high = (await client.post("/api/v1/rules", json={"name": "Hot lead", "entity_type": "lead", "priority": 300,
        "conflict_strategy": "highest_priority", "definition": _hot_lead_def()}, headers=d["h_admin"])).json()
    # list is ordered by priority desc (execution order)
    rules = (await client.get("/api/v1/rules", params={"entity_type": "lead"}, headers=d["h_admin"])).json()
    assert rules[0]["id"] == high["id"] and rules[-1]["id"] == low["id"]
    # resolve against a hot lead → both match, winner is the highest priority
    lead = Lead(organization_id=d["org"].id, last_name="Big", title="Deal", status="New", value=90000,
                created_by=d["admin"].id, stage_id=d["stage"].id)
    db.add(lead); await db.commit()
    out = (await client.post("/api/v1/rules/resolve", json={"entity_type": "lead", "entity_id": str(lead.id)}, headers=d["h_admin"])).json()
    assert len(out["matched"]) == 2 and out["winner"]["name"] == "Hot lead"
    # priority endpoint
    bumped = (await client.post(f"/api/v1/rules/{low['id']}/priority", json={"priority": 500}, headers=d["h_admin"])).json()
    assert bumped["priority"] == 500


@pytest.mark.asyncio
async def test_templates_clone_export_import(client: AsyncClient, setup: dict):
    d = setup
    seeded = (await client.post("/api/v1/rules/templates/seed", json={}, headers=d["h_admin"])).json()
    assert seeded["created"] >= 1
    tpls = (await client.get("/api/v1/rules", params={"is_template": True}, headers=d["h_admin"])).json()
    inst = (await client.post(f"/api/v1/rules/templates/{tpls[0]['id']}/instantiate", headers=d["h_admin"])).json()
    assert inst["is_template"] is False and inst["is_active"] is True
    # clone
    cl = (await client.post(f"/api/v1/rules/{inst['id']}/clone", headers=d["h_admin"])).json()
    assert cl["name"].endswith("(copy)")
    # export → import round-trip
    exported = (await client.get(f"/api/v1/rules/{inst['id']}/export", headers=d["h_admin"])).json()
    assert exported["_format"] == "crm.rule.v1"
    imp = (await client.post("/api/v1/rules/import", json=exported, headers=d["h_admin"])).json()
    assert imp["entity_type"] == inst["entity_type"] and imp["condition_count"] == inst["condition_count"]


@pytest.mark.asyncio
async def test_reports_dashboard_and_evaluations(client: AsyncClient, setup: dict):
    d = setup
    r = (await client.post("/api/v1/rules", json={"name": "Hot lead", "entity_type": "lead",
        "definition": _hot_lead_def()}, headers=d["h_admin"])).json()
    await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"value": 60000, "status": "New"}}, headers=d["h_admin"])
    rep = (await client.get("/api/v1/rules/report", headers=d["h_admin"])).json()
    assert rep["total"] >= 1 and rep["evaluations"] >= 1 and "lead" in rep["by_entity"]
    dash = (await client.get("/api/v1/rules/dashboard", headers=d["h_admin"])).json()
    assert "match_rate" in dash and "top" in dash
    evs = (await client.get("/api/v1/rules/evaluations", headers=d["h_admin"])).json()
    assert len(evs) >= 1 and evs[0]["is_test"] is True


@pytest.mark.asyncio
async def test_workflow_engine_consumes_rule_group_conditions(client: AsyncClient, setup: dict, db: AsyncSession):
    """Backward-compat + integration: a workflow trigger node using the new
    group-condition format is honoured by the engine's _match_conditions."""
    from app.services.workflow_engine_service import WorkflowEngineService
    svc = WorkflowEngineService(db)

    class _E:  # lightweight fake lead
        pass
    e = _E(); e.value = 90000; e.status = "New"; e.source = "Website"
    grp = _hot_lead_def()
    assert svc._match_conditions(e, grp) is True
    e2 = _E(); e2.value = 100; e2.status = "New"; e2.source = "Website"
    assert svc._match_conditions(e2, grp) is False
    # flat legacy format still works unchanged
    assert svc._match_conditions(e, [{"field": "status", "op": "eq", "value": "New"}]) is True


# ---------------- Business Rule Designer ----------------
@pytest.mark.asyncio
async def test_user_variables_used_in_expression(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/rules/catalog", headers=d["h_admin"])).json()
    assert "notify_owner" in cat["action_types"] and "number" in cat["variable_value_types"]
    # employee cannot create a variable
    assert (await client.post("/api/v1/rules/variables", json={"name": "min_value", "value_type": "number", "value": 50000}, headers=d["h_emp"])).status_code == 403
    v = (await client.post("/api/v1/rules/variables", json={
        "name": "min_value", "value_type": "number", "value": 50000}, headers=d["h_admin"])).json()
    assert v["resolved"] == 50000
    # duplicate name rejected
    assert (await client.post("/api/v1/rules/variables", json={"name": "min_value", "value_type": "number", "value": 1}, headers=d["h_admin"])).status_code == 409
    # a rule that references the org variable
    r = (await client.post("/api/v1/rules", json={"name": "Big deal", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value_type": "variable", "variable": "min_value"}]}},
        headers=d["h_admin"])).json()
    assert (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"value": 60000}}, headers=d["h_admin"])).json()["matched"] is True
    assert (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"value": 100}}, headers=d["h_admin"])).json()["matched"] is False
    # an unknown variable is rejected at validation
    bad = await client.post("/api/v1/rules", json={"name": "bad", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value_type": "variable", "variable": "ghost"}]}},
        headers=d["h_admin"])
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_reusable_components_expand_and_cycle_guard(client: AsyncClient, setup: dict):
    d = setup
    comp = (await client.post("/api/v1/rules/components", json={
        "name": "Is New", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "status", "op": "eq", "value": "New"}]}}, headers=d["h_admin"])).json()
    # a rule that references the component alongside its own condition
    r = (await client.post("/api/v1/rules", json={"name": "New & big", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "ref", "ref_id": comp["id"]},
            {"type": "condition", "field": "value", "op": "gte", "value": 1000}]}}, headers=d["h_admin"])).json()
    assert (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"status": "New", "value": 5000}}, headers=d["h_admin"])).json()["matched"] is True
    assert (await client.post(f"/api/v1/rules/{r['id']}/test", json={"sample": {"status": "Lost", "value": 5000}}, headers=d["h_admin"])).json()["matched"] is False
    # referencing a missing component fails
    bad = await client.post("/api/v1/rules", json={"name": "bad", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [
            {"type": "ref", "ref_id": str(uuid.uuid4())}]}}, headers=d["h_admin"])
    assert bad.status_code == 400
    # form a latent cycle between two components (B→A, then A→B) and prove the
    # guard trips when a rule tries to expand the cycle.
    comp_b = (await client.post("/api/v1/rules/components", json={
        "name": "Wraps New", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [{"type": "ref", "ref_id": comp["id"]}]}},
        headers=d["h_admin"])).json()
    assert (await client.patch(f"/api/v1/rules/components/{comp['id']}", json={
        "definition": {"type": "group", "logic": "and", "children": [{"type": "ref", "ref_id": comp_b["id"]}]}},
        headers=d["h_admin"])).status_code == 200
    cyc = await client.post("/api/v1/rules", json={"name": "cyclic", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": [{"type": "ref", "ref_id": comp["id"]}]}},
        headers=d["h_admin"])
    assert cyc.status_code == 400


@pytest.mark.asyncio
async def test_rule_actions_and_simulation(client: AsyncClient, setup: dict, db: AsyncSession):
    from app.models.notification import Notification
    d = setup
    # invalid action type rejected
    assert (await client.post("/api/v1/rules", json={"name": "bad", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": []},
        "actions": [{"type": "delete_everything"}]}, headers=d["h_admin"])).status_code == 400
    # a rule that matches every lead and notifies the Employee role
    r = (await client.post("/api/v1/rules", json={"name": "Touch all", "entity_type": "lead",
        "definition": {"type": "group", "logic": "and", "children": []},
        "actions": [{"type": "notify_role", "role": "Employee", "message": "A lead matched"}]}, headers=d["h_admin"])).json()
    assert r["action_count"] == 1
    lead = Lead(organization_id=d["org"].id, last_name="X", title="Deal", status="New", value=10,
                created_by=d["admin"].id, stage_id=d["stage"].id)
    db.add(lead); await db.commit()
    # dry-run simulation: matches but fires nothing
    dry = (await client.post(f"/api/v1/rules/{r['id']}/simulate", json={"limit": 50, "execute": False}, headers=d["h_admin"])).json()
    assert dry["evaluated"] >= 1 and dry["matched"] >= 1 and dry["executed"] == 0
    assert (await db.execute(select(Notification).filter(Notification.user_id == d["emp"].id, Notification.category == "rule"))).scalars().first() is None
    # execute=true fires the action → the employee is notified
    run = (await client.post(f"/api/v1/rules/{r['id']}/simulate", json={"limit": 50, "execute": True}, headers=d["h_admin"])).json()
    assert run["executed"] >= 1
    assert (await db.execute(select(Notification).filter(Notification.user_id == d["emp"].id, Notification.category == "rule"))).scalars().first() is not None
    # employees cannot simulate
    assert (await client.post(f"/api/v1/rules/{r['id']}/simulate", json={"execute": True}, headers=d["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_versioning_restore_and_audit(client: AsyncClient, setup: dict):
    d = setup
    r = (await client.post("/api/v1/rules", json={"name": "Verd", "entity_type": "lead", "priority": 100,
        "definition": _hot_lead_def()}, headers=d["h_admin"])).json()
    # a structural update snapshots the prior state
    await client.patch(f"/api/v1/rules/{r['id']}", json={"priority": 300}, headers=d["h_admin"])
    versions = (await client.get(f"/api/v1/rules/{r['id']}/versions", headers=d["h_admin"])).json()
    assert len(versions) >= 2
    v1 = min(versions, key=lambda v: v["version_no"])
    assert v1["snapshot"]["priority"] == 100
    # restore the original priority
    restored = (await client.post(f"/api/v1/rules/{r['id']}/versions/restore", json={"version_no": v1["version_no"]}, headers=d["h_admin"])).json()
    assert restored["priority"] == 100
    # audit log surfaces the rule lifecycle events
    audit = (await client.get("/api/v1/rules/audit", headers=d["h_admin"])).json()
    actions = {a["action"] for a in audit}
    assert "RULE_CREATED" in actions and "RULE_UPDATED" in actions and "RULE_RESTORED" in actions

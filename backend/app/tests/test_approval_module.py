import pytest
import uuid
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.notification import Notification
from app.models.approval import ApprovalRequest, ApprovalChain, ApprovalAction
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
    org = await org_repo.create({"name": "Appr Org", "slug": "appr-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@ap.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@ap.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    emp = await user_repo.create_user(org.id, {
        "email": "emp@ap.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    peer = await user_repo.create_user(org.id, {
        "email": "peer@ap.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Peer", "last_name": "Three", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp, "peer": peer,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
        "h_peer": {"Authorization": f"Bearer {create_access_token(peer.id)}"},
    }


async def _chain(client, headers, **over):
    payload = {"name": "Expense chain", "request_type": "expense", "min_amount": 0,
               "steps": [{"approver_role": "Manager"}, {"approver_role": "OrgAdmin"}]}
    payload.update(over)
    return await client.post("/api/v1/approvals/chains", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_chain_crud_permissions_and_validation(client: AsyncClient, setup: dict):
    data = setup
    assert (await _chain(client, data["h_emp"])).status_code == 403
    c = (await _chain(client, data["h_admin"])).json()
    assert len(c["steps"]) == 2 and c["steps"][0]["level"] == 1
    # invalid type
    assert (await _chain(client, data["h_admin"], name="x", request_type="teleport")).status_code == 400
    # step with neither role nor user
    assert (await _chain(client, data["h_admin"], name="y", steps=[{"approver_role": None, "approver_user_id": None}])).status_code == 400


@pytest.mark.asyncio
async def test_multi_level_approval_flow_and_history(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _chain(client, data["h_admin"])  # Manager → OrgAdmin (2 levels)
    # employee submits an expense
    r = await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Taxi", "amount": 500}, headers=data["h_emp"])
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending" and req["current_level"] == 1 and req["total_levels"] == 2
    # level-1 approver (the employee's manager) is notified
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.title == "Approval needed"))).scalars().first() is not None

    # a peer employee cannot approve
    assert (await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_peer"])).status_code == 403
    # manager approves level 1 → advances to level 2 (still pending)
    r = await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["current_level"] == 2
    # manager cannot approve level 2 (that's OrgAdmin) — but manager is not OrgAdmin
    # (manager is not an eligible approver at level 2 and not admin) → 403
    assert (await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_mgr"])).status_code == 403
    # OrgAdmin approves level 2 → approved
    r = await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True, "note": "ok"}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # requester notified of approval
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.title == "Request approved"))).scalars().first() is not None
    # history has submitted + 2 approvals
    hist = (await client.get(f"/api/v1/approvals/{req['id']}/history", headers=data["h_emp"])).json()
    actions = [h["action"] for h in hist]
    assert actions.count("approved") == 2 and "submitted" in actions


@pytest.mark.asyncio
async def test_reject_and_amount_tiered_chain(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # low tier: single level (Manager); high tier (>=1000): two levels
    await client.post("/api/v1/approvals/chains", json={
        "name": "Discount low", "request_type": "discount", "min_amount": 0,
        "steps": [{"approver_role": "Manager"}]}, headers=data["h_admin"])
    await client.post("/api/v1/approvals/chains", json={
        "name": "Discount high", "request_type": "discount", "min_amount": 1000,
        "steps": [{"approver_role": "Manager"}, {"approver_role": "OrgAdmin"}]}, headers=data["h_admin"])
    # a 200 discount → low chain (1 level)
    low = (await client.post("/api/v1/approvals", json={
        "request_type": "discount", "title": "5% off", "amount": 200}, headers=data["h_emp"])).json()
    assert low["total_levels"] == 1
    # a 5000 discount → high chain (2 levels)
    high = (await client.post("/api/v1/approvals", json={
        "request_type": "discount", "title": "big off", "amount": 5000}, headers=data["h_emp"])).json()
    assert high["total_levels"] == 2
    # manager rejects the low one → rejected immediately
    r = await client.post(f"/api/v1/approvals/{low['id']}/act", json={"approve": False, "note": "no"}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_delegation_lets_delegate_act(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _chain(client, data["h_admin"], name="Exp", steps=[{"approver_role": "Manager"}])  # single level = manager
    # manager delegates their approvals to the peer employee
    r = await client.post("/api/v1/approvals/delegations", json={
        "delegate_id": str(data["peer"].id), "request_type": "expense"}, headers=data["h_mgr"])
    assert r.status_code == 201
    # employee submits
    req = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Lunch", "amount": 100}, headers=data["h_emp"])).json()
    # the delegate (peer) can now approve on the manager's behalf
    r = await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_peer"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # the action recorded on_behalf_of the manager
    act = (await db.execute(select(ApprovalAction).filter(
        ApprovalAction.request_id == uuid.UUID(req["id"]), ApprovalAction.action == "approved"))).scalars().first()
    assert act.on_behalf_of == data["mgr"].id and act.actor_id == data["peer"].id
    # revoke → delegate can no longer act on a new request
    delegs = (await client.get("/api/v1/approvals/delegations", headers=data["h_mgr"])).json()
    await client.post(f"/api/v1/approvals/delegations/{delegs[0]['id']}/revoke", json={}, headers=data["h_mgr"])
    req2 = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Dinner", "amount": 100}, headers=data["h_emp"])).json()
    assert (await client.post(f"/api/v1/approvals/{req2['id']}/act", json={"approve": True}, headers=data["h_peer"])).status_code == 403


@pytest.mark.asyncio
async def test_pending_box_escalation_dashboard_and_workflow(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _chain(client, data["h_admin"], name="Exp2", steps=[{"approver_role": "Manager"}], escalation_hours=1)
    # workflow rule on approval_approved → notify the requester's manager
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Appr done", "trigger_event": "approval_approved", "conditions": [],
        "actions": [{"type": "notify_manager", "message": "Approved!"}]}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text

    req = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Fuel", "amount": 300}, headers=data["h_emp"])).json()
    # manager's "pending my action" box shows it
    pend = (await client.get("/api/v1/approvals", params={"box": "pending"}, headers=data["h_mgr"])).json()
    assert any(x["id"] == req["id"] for x in pend["items"])
    # employee's box shows their own
    mine = (await client.get("/api/v1/approvals", params={"box": "mine"}, headers=data["h_emp"])).json()
    assert mine["total"] == 1

    # force the request old and escalate
    row = (await db.execute(select(ApprovalRequest).filter(ApprovalRequest.id == uuid.UUID(req["id"])))).scalars().first()
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await db.commit()
    esc = (await client.post("/api/v1/approvals/escalate-overdue", json={}, headers=data["h_admin"])).json()
    assert esc["escalated"] == 1
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["admin"].id, Notification.title == "Approval escalated"))).scalars().first() is not None

    # manager approves → workflow fires (manager gets "Workflow: Appr done")
    await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_mgr"])
    wf = (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.category == "approval",
        Notification.title == "Workflow: Appr done"))).scalars().first()
    assert wf is not None

    # dashboard + report
    dash = (await client.get("/api/v1/approvals/dashboard", headers=data["h_mgr"])).json()
    assert "awaiting_my_action" in dash and dash["approved"] >= 1
    rep = (await client.get("/api/v1/approvals/report", headers=data["h_mgr"])).json()
    assert any(row["request_type"] == "expense" for row in rep["rows"])
    # invalid workflow action for approval entity rejected
    bad = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad", "trigger_event": "approval_rejected", "conditions": [],
        "actions": [{"type": "set_status", "value": "x"}]}, headers=data["h_admin"])
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_dynamic_chain_conditions_and_auto_approve_reject(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # dynamic routing: a conditional chain (payload.category == travel) beats the generic one
    await _chain(client, data["h_admin"], name="Travel", request_type="expense",
                 conditions={"field": "category", "op": "eq", "value": "travel"},
                 steps=[{"approver_role": "Manager"}, {"approver_role": "OrgAdmin"}])
    await _chain(client, data["h_admin"], name="General", request_type="expense",
                 steps=[{"approver_role": "Manager"}],
                 auto_approve_conditions={"field": "amount", "op": "lt", "value": 100},
                 auto_reject_conditions={"field": "amount", "op": "gt", "value": 100000})
    travel = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Flight", "amount": 500,
        "payload": {"category": "travel"}}, headers=data["h_emp"])).json()
    assert travel["total_levels"] == 2  # routed to the conditional Travel chain
    other = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Chair", "amount": 500,
        "payload": {"category": "office"}}, headers=data["h_emp"])).json()
    assert other["total_levels"] == 1 and other["status"] == "pending"  # generic chain
    # auto-approve: tiny amount decided instantly, no approver involved
    small = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Pens", "amount": 50}, headers=data["h_emp"])).json()
    assert small["status"] == "approved"
    hist = (await client.get(f"/api/v1/approvals/{small['id']}/history", headers=data["h_emp"])).json()
    assert any(h["action"] == "auto_approved" for h in hist)
    # auto-reject: absurd amount rejected instantly + requester notified
    huge = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Yacht", "amount": 5000000}, headers=data["h_emp"])).json()
    assert huge["status"] == "rejected"
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.title == "Request rejected"))).scalars().first() is not None


@pytest.mark.asyncio
async def test_parallel_all_mode_level(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    from app.repositories.user_repository import UserRepository
    admin2 = await UserRepository(db).create_user(data["org"].id, {
        "email": "admin2@ap.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "Two", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    h_admin2 = {"Authorization": f"Bearer {create_access_token(admin2.id)}"}
    # one parallel level: EVERY OrgAdmin must approve
    await _chain(client, data["h_admin"], name="Quote", request_type="quotation",
                 steps=[{"approver_role": "OrgAdmin", "mode": "all"}])
    req = (await client.post("/api/v1/approvals", json={
        "request_type": "quotation", "title": "Q-42", "amount": 900}, headers=data["h_emp"])).json()
    # first admin approves → level not complete, still pending
    r = await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_admin"])
    assert r.status_code == 200 and r.json()["status"] == "pending"
    # same admin cannot approve the level twice
    assert (await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_admin"])).status_code == 409
    # second admin completes the parallel level → approved
    r = await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=h_admin2)
    assert r.status_code == 200 and r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_conditional_step_skip(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # level 2 only applies to amounts >= 1000
    await _chain(client, data["h_admin"], name="Disc", request_type="discount",
                 steps=[{"approver_role": "Manager"},
                        {"approver_role": "OrgAdmin", "conditions": {"field": "amount", "op": "gte", "value": 1000}}])
    low = (await client.post("/api/v1/approvals", json={
        "request_type": "discount", "title": "small", "amount": 200}, headers=data["h_emp"])).json()
    # manager approves L1 → L2 skipped by conditions → fully approved
    r = await client.post(f"/api/v1/approvals/{low['id']}/act", json={"approve": True}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    high = (await client.post("/api/v1/approvals", json={
        "request_type": "discount", "title": "big", "amount": 5000}, headers=data["h_emp"])).json()
    r = await client.post(f"/api/v1/approvals/{high['id']}/act", json={"approve": True}, headers=data["h_mgr"])
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["current_level"] == 2
    # a request whose FIRST level is skipped starts at the next active level
    await _chain(client, data["h_admin"], name="Tgt", request_type="target",
                 steps=[{"approver_role": "Manager", "conditions": {"field": "amount", "op": "gte", "value": 1000}},
                        {"approver_role": "OrgAdmin"}])
    skip1 = (await client.post("/api/v1/approvals", json={
        "request_type": "target", "title": "t", "amount": 10}, headers=data["h_emp"])).json()
    assert skip1["current_level"] == 2 and skip1["status"] == "pending"


async def _backdate(db: AsyncSession, request_id: str, hours: int):
    old = datetime.now(timezone.utc) - timedelta(hours=hours)
    req = (await db.execute(select(ApprovalRequest).filter(ApprovalRequest.id == uuid.UUID(request_id)))).scalars().first()
    req.created_at = old
    acts = list((await db.execute(select(ApprovalAction).filter(
        ApprovalAction.request_id == uuid.UUID(request_id)))).scalars().all())
    for a in acts:
        a.created_at = old
    await db.commit()


@pytest.mark.asyncio
async def test_timeouts_and_requested_workflow_trigger(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # a workflow rule on the new approval_requested trigger fires on submit
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "New appr", "trigger_event": "approval_requested", "conditions": [],
        "actions": [{"type": "notify_manager", "message": "Look at this"}]}, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text

    await _chain(client, data["h_admin"], name="ExpTO", request_type="expense",
                 steps=[{"approver_role": "Manager"}], timeout_hours=1, timeout_action="auto_reject")
    await _chain(client, data["h_admin"], name="QuoteTO", request_type="quotation",
                 steps=[{"approver_role": "Manager"}], timeout_hours=1, timeout_action="escalate")
    await _chain(client, data["h_admin"], name="DiscTO", request_type="discount",
                 steps=[{"approver_role": "Manager"}], timeout_hours=1, timeout_action="auto_approve")

    exp = (await client.post("/api/v1/approvals", json={
        "request_type": "expense", "title": "Stuck expense", "amount": 300}, headers=data["h_emp"])).json()
    # the approval_requested workflow notified the requester's manager
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["mgr"].id, Notification.title == "Workflow: New appr"))).scalars().first() is not None
    quo = (await client.post("/api/v1/approvals", json={
        "request_type": "quotation", "title": "Stuck quote", "amount": 300}, headers=data["h_emp"])).json()
    dis = (await client.post("/api/v1/approvals", json={
        "request_type": "discount", "title": "Stuck discount", "amount": 300}, headers=data["h_emp"])).json()

    for rid in (exp["id"], quo["id"], dis["id"]):
        await _backdate(db, rid, 3)
    # employees cannot run it; admin can
    assert (await client.post("/api/v1/approvals/process-timeouts", json={}, headers=data["h_emp"])).status_code == 403
    out = (await client.post("/api/v1/approvals/process-timeouts", json={}, headers=data["h_admin"])).json()
    assert out["processed"] == 3 and out["auto_rejected"] == 1 and out["escalated"] == 1 and out["auto_approved"] == 1

    exp2 = (await client.get("/api/v1/approvals", params={"box": "mine", "status": "rejected"}, headers=data["h_emp"])).json()
    assert any(x["id"] == exp["id"] for x in exp2["items"])
    dis2 = (await client.get("/api/v1/approvals", params={"box": "mine", "status": "approved"}, headers=data["h_emp"])).json()
    assert any(x["id"] == dis["id"] for x in dis2["items"])
    quo_row = (await db.execute(select(ApprovalRequest).filter(ApprovalRequest.id == uuid.UUID(quo["id"])))).scalars().first()
    assert quo_row.escalated is True and quo_row.status == "pending"
    # escalation notified the admins
    assert (await db.execute(select(Notification).filter(
        Notification.user_id == data["admin"].id, Notification.title == "Approval escalated"))).scalars().first() is not None
    # running again is idempotent (escalated flag dedups; decided ones are gone)
    out2 = (await client.post("/api/v1/approvals/process-timeouts", json={}, headers=data["h_admin"])).json()
    assert out2["processed"] == 0


@pytest.mark.asyncio
async def test_no_chain_routes_to_admin_and_cancel(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # no chain configured for 'generic' → routes straight to OrgAdmin, 1 level
    req = (await client.post("/api/v1/approvals", json={
        "request_type": "generic", "title": "Misc"}, headers=data["h_emp"])).json()
    assert req["total_levels"] == 1
    pend = (await client.get("/api/v1/approvals", params={"box": "pending"}, headers=data["h_admin"])).json()
    assert any(x["id"] == req["id"] for x in pend["items"])
    # requester cancels
    r = await client.post(f"/api/v1/approvals/{req['id']}/cancel", json={}, headers=data["h_emp"])
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # cannot act on a cancelled request
    assert (await client.post(f"/api/v1/approvals/{req['id']}/act", json={"approve": True}, headers=data["h_admin"])).status_code == 409

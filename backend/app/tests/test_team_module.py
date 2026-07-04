import pytest
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.task import Task
from app.models.calendar_event import CalendarEvent
from app.models.pipeline import PipelineStage
from app.models.notification import Notification
from app.models.team import TeamMember
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
    org = await org_repo.create({"name": "Team Org", "slug": "team-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@team.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@team.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id})
    tl = await user_repo.create_user(org.id, {
        "email": "tl@team.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Tl", "last_name": "Lead", "role": "Employee", "is_active": True,
        "reporting_to_id": mgr.id})
    emp1 = await user_repo.create_user(org.id, {
        "email": "emp1@team.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "One", "role": "Employee", "is_active": True,
        "reporting_to_id": tl.id})
    emp2 = await user_repo.create_user(org.id, {
        "email": "emp2@team.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": tl.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "mgr": mgr, "tl": tl, "emp1": emp1, "emp2": emp2, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_mgr": {"Authorization": f"Bearer {create_access_token(mgr.id)}"},
        "h_tl": {"Authorization": f"Bearer {create_access_token(tl.id)}"},
        "h_emp1": {"Authorization": f"Bearer {create_access_token(emp1.id)}"},
    }


async def _mk(client, headers, **over):
    payload = {"name": "Alpha", "code": "ALPHA", "capacity": 5}
    payload.update(over)
    return await client.post("/api/v1/teams", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_create_edit_permissions_and_uniqueness(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # employee cannot create; Manager and OrgAdmin can
    assert (await _mk(client, data["h_emp1"])).status_code == 403
    r = await _mk(client, data["h_mgr"], team_leader_id=str(data["tl"].id))
    assert r.status_code == 201, r.text
    team = r.json()
    assert team["leader_name"] == "Tl Lead" and team["member_count"] == 1  # leader auto-membered
    # leader got a notification
    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["tl"].id, Notification.category == "team"))).scalars().first()
    assert notif is not None
    # duplicate name rejected
    assert (await _mk(client, data["h_admin"])).status_code == 409
    # edit: TL can rename their own team; outsider employee cannot
    r = await client.patch(f"/api/v1/teams/{team['id']}", json={"description": "tl edit"},
                           headers=data["h_tl"])
    assert r.status_code == 200
    r = await client.patch(f"/api/v1/teams/{team['id']}", json={"team_leader_id": str(data['emp1'].id)},
                           headers=data["h_tl"])
    assert r.status_code == 403  # only managers change leaders


@pytest.mark.asyncio
async def test_members_capacity_guard_and_removal(client: AsyncClient, setup: dict):
    data = setup
    team = (await _mk(client, data["h_admin"], name="CapTeam", capacity=2,
                      team_leader_id=str(data["tl"].id))).json()
    # leader occupies 1 of 2 seats; adding two more exceeds capacity
    r = await client.post(f"/api/v1/teams/{team['id']}/members",
                          json={"user_ids": [str(data["emp1"].id), str(data["emp2"].id)]},
                          headers=data["h_admin"])
    assert r.status_code == 409
    r = await client.post(f"/api/v1/teams/{team['id']}/members",
                          json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    assert r.json()["added"] == 1
    members = (await client.get(f"/api/v1/teams/{team['id']}/members", headers=data["h_admin"])).json()
    assert {m["email"] for m in members} == {"tl@team.com", "emp1@team.com"}
    # capacity cannot drop below member count
    r = await client.patch(f"/api/v1/teams/{team['id']}", json={"capacity": 1}, headers=data["h_admin"])
    assert r.status_code == 400
    # leader cannot be removed
    r = await client.post(f"/api/v1/teams/{team['id']}/members/remove",
                          json={"user_ids": [str(data["tl"].id)]}, headers=data["h_admin"])
    assert r.status_code == 400
    # member removal works
    r = await client.post(f"/api/v1/teams/{team['id']}/members/remove",
                          json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    assert r.json()["removed"] == 1


@pytest.mark.asyncio
async def test_leader_change_updates_membership(client: AsyncClient, setup: dict):
    data = setup
    team = (await _mk(client, data["h_admin"], name="LeadSwap",
                      team_leader_id=str(data["tl"].id))).json()
    r = await client.patch(f"/api/v1/teams/{team['id']}",
                           json={"team_leader_id": str(data["emp1"].id)}, headers=data["h_mgr"])
    assert r.status_code == 200
    members = (await client.get(f"/api/v1/teams/{team['id']}/members", headers=data["h_admin"])).json()
    roles = {m["email"]: m["role_in_team"] for m in members}
    assert roles["emp1@team.com"] == "leader" and roles["tl@team.com"] == "member"


@pytest.mark.asyncio
async def test_targets_and_performance_rollup(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    team = (await _mk(client, data["h_admin"], name="PerfTeam",
                      team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{team['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    # TL can set targets
    r = await client.post(f"/api/v1/teams/{team['id']}/targets", json={
        "name": "Q3 conversions", "metric": "leads_converted", "target_value": 2}, headers=data["h_tl"])
    assert r.status_code == 201, r.text
    assert (await client.post(f"/api/v1/teams/{team['id']}/targets", json={
        "name": "bad", "metric": "nope", "target_value": 1}, headers=data["h_admin"])).status_code == 400

    # one converted lead assigned to a member
    db.add(Lead(organization_id=data["org"].id, last_name="Won", title="W", status="Won",
                value=500, created_by=data["admin"].id, assigned_user_id=data["emp1"].id,
                stage_id=data["stage"].id))
    db.add(Task(organization_id=data["org"].id, title="Done task", status="Done",
                created_by=data["admin"].id, assigned_user_id=data["emp1"].id))
    await db.commit()

    perf = (await client.get(f"/api/v1/teams/{team['id']}/performance", headers=data["h_tl"])).json()
    assert perf["metrics"]["leads_converted"] == 1
    assert perf["metrics"]["tasks_completed"] == 1
    assert perf["metrics"]["revenue"] == 500.0
    kpi = perf["kpis"][0]
    assert kpi["attainment"] == 50.0
    assert any(m["user_id"] == str(data["emp1"].id) and m["leads_converted"] == 1
               for m in perf["members"])


@pytest.mark.asyncio
async def test_lead_assignment_round_robin_and_leader(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    team = (await _mk(client, data["h_admin"], name="AssignTeam",
                      team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{team['id']}/members",
                      json={"user_ids": [str(data["emp1"].id), str(data["emp2"].id)]},
                      headers=data["h_admin"])
    leads = []
    for i in range(6):
        lead = Lead(organization_id=data["org"].id, last_name=f"L{i}", title=f"L{i}", status="New",
                    created_by=data["admin"].id, stage_id=data["stage"].id)
        db.add(lead)
        leads.append(lead)
    await db.commit()

    r = await client.post(f"/api/v1/teams/{team['id']}/assign-leads",
                          json={"lead_ids": [str(l.id) for l in leads[:4]], "strategy": "round_robin"},
                          headers=data["h_tl"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assigned"] == 4
    # least-loaded distribution across the 3 members is balanced (max-min <= 1)
    dist = body["distribution"].values()
    assert max(dist) - min(dist) <= 1

    r = await client.post(f"/api/v1/teams/{team['id']}/assign-leads",
                          json={"lead_ids": [str(leads[4].id)], "strategy": "leader"},
                          headers=data["h_mgr"])
    assert r.json()["distribution"] == {str(data["tl"].id): 1}

    # plain employee (non-leader) cannot assign
    r = await client.post(f"/api/v1/teams/{team['id']}/assign-leads",
                          json={"lead_ids": [str(leads[5].id)]}, headers=data["h_emp1"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_task_assignment(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    team = (await _mk(client, data["h_admin"], name="TaskTeam",
                      team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{team['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    tasks = []
    for i in range(2):
        t = Task(organization_id=data["org"].id, title=f"T{i}", status="Todo",
                 created_by=data["admin"].id)
        db.add(t)
        tasks.append(t)
    await db.commit()
    r = await client.post(f"/api/v1/teams/{team['id']}/assign-tasks",
                          json={"task_ids": [str(t.id) for t in tasks]}, headers=data["h_tl"])
    assert r.status_code == 200 and r.json()["assigned"] == 2
    await db.refresh(tasks[0])
    assert tasks[0].assigned_user_id in (data["tl"].id, data["emp1"].id)


@pytest.mark.asyncio
async def test_team_calendar_aggregation(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    team = (await _mk(client, data["h_admin"], name="CalTeam",
                      team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{team['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    now = datetime.now(timezone.utc)
    db.add(CalendarEvent(organization_id=data["org"].id, title="Standup",
                         start_at=now + timedelta(hours=1), end_at=now + timedelta(hours=2),
                         assigned_user_id=data["emp1"].id, created_by=data["tl"].id))
    db.add(Task(organization_id=data["org"].id, title="Due task", status="Todo",
                due_date=now + timedelta(hours=3), created_by=data["tl"].id,
                assigned_user_id=data["tl"].id))
    await db.commit()
    r = await client.get(f"/api/v1/teams/{team['id']}/calendar",
                         params={"date_from": (now - timedelta(days=1)).isoformat(),
                                 "date_to": (now + timedelta(days=1)).isoformat()},
                         headers=data["h_tl"])
    assert r.status_code == 200, r.text
    kinds = {(i["type"], i["title"]) for i in r.json()}
    assert ("event", "Standup") in kinds and ("task", "Due task") in kinds


@pytest.mark.asyncio
async def test_visibility_scoping_search_dashboard_analytics(client: AsyncClient, setup: dict):
    data = setup
    t1 = (await _mk(client, data["h_admin"], name="Visible", code="VIS",
                    team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{t1['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    (await _mk(client, data["h_admin"], name="Hidden Team", code="HID")).json()

    # manager sees both; member employee sees only their team
    all_list = (await client.get("/api/v1/teams", headers=data["h_mgr"])).json()
    assert all_list["total"] == 2
    emp_list = (await client.get("/api/v1/teams", headers=data["h_emp1"])).json()
    assert emp_list["total"] == 1 and emp_list["items"][0]["name"] == "Visible"
    # non-member cannot open a hidden team's detail
    hidden_id = next(t["id"] for t in all_list["items"] if t["name"] == "Hidden Team")
    assert (await client.get(f"/api/v1/teams/{hidden_id}", headers=data["h_emp1"])).status_code == 403

    # search + filters
    r = (await client.get("/api/v1/teams", params={"search": "VIS"}, headers=data["h_admin"])).json()
    assert r["total"] == 1
    r = (await client.get("/api/v1/teams", params={"leader_id": str(data["tl"].id)},
                          headers=data["h_admin"])).json()
    assert r["total"] == 1

    # dashboard + analytics + report
    dash = (await client.get("/api/v1/teams/dashboard", headers=data["h_admin"])).json()
    assert dash["total"] == 2 and dash["total_members"] == 2
    rows = (await client.get("/api/v1/teams/analytics", headers=data["h_admin"])).json()
    assert {row["name"] for row in rows} == {"Visible", "Hidden Team"}
    rep = (await client.get("/api/v1/teams/report", headers=data["h_admin"])).json()
    assert rep["summary"]["total"] == 2 and len(rep["teams"]) == 2


@pytest.mark.asyncio
async def test_bulk_actions_and_delete_guard(client: AsyncClient, setup: dict):
    data = setup
    t1 = (await _mk(client, data["h_admin"], name="Bulk1")).json()
    t2 = (await _mk(client, data["h_admin"], name="Bulk2", team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{t2['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])
    r = await client.post("/api/v1/teams/bulk", json={
        "team_ids": [t1["id"], t2["id"]], "action": "archive"}, headers=data["h_admin"])
    assert r.json()["processed"] == 2
    # delete blocked while members (beyond the leader) remain
    r = await client.post("/api/v1/teams/bulk", json={
        "team_ids": [t1["id"], t2["id"]], "action": "delete"}, headers=data["h_admin"])
    body = r.json()
    assert body["processed"] == 1 and len(body["errors"]) == 1
    assert (await client.delete(f"/api/v1/teams/{t1['id']}", headers=data["h_admin"])).status_code == 404


@pytest.mark.asyncio
async def test_import_export_csv(client: AsyncClient, setup: dict):
    data = setup
    csv_content = ("name,code,description,leader_email,capacity,status\n"
                   "Imported A,IMA,first,tl@team.com,4,active\n"
                   "Imported B,IMB,second,,,active\n"
                   "Imported C,IMC,bad leader,nobody@x.com,,active\n")
    r = await client.post("/api/v1/teams/import",
                          files={"file": ("teams.csv", csv_content, "text/csv")},
                          headers=data["h_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 3 and len(body["errors"]) == 1
    r = await client.get("/api/v1/teams/export", headers=data["h_admin"])
    assert r.status_code == 200
    assert "Imported A" in r.text and "tl@team.com" in r.text
    # import is manager+ only
    r = await client.post("/api/v1/teams/import",
                          files={"file": ("teams.csv", csv_content, "text/csv")},
                          headers=data["h_emp1"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_workflow_assign_to_team_action(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    team = (await _mk(client, data["h_admin"], name="WfTeam",
                      team_leader_id=str(data["tl"].id))).json()
    await client.post(f"/api/v1/teams/{team['id']}/members",
                      json={"user_ids": [str(data["emp1"].id)]}, headers=data["h_admin"])

    from app.services.workflow_service import WorkflowService
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Team router", "trigger_event": "lead_created",
        "conditions": [], "actions": [{"type": "assign_to_team", "team_id": team["id"]}],
    }, headers=data["h_admin"])
    assert r.status_code in (200, 201), r.text

    lead = Lead(organization_id=data["org"].id, last_name="Wf", title="WF Lead", status="New",
                created_by=data["admin"].id, stage_id=data["stage"].id)
    db.add(lead)
    await db.commit()
    applied = await WorkflowService(db).run("lead_created", lead, data["admin"])
    await db.commit()
    assert "assign_to_team" in applied
    member_ids = {m.user_id for m in (await db.execute(select(TeamMember).filter(
        TeamMember.team_id == uuid.UUID(team["id"])))).scalars().all()}
    assert lead.assigned_user_id in member_ids

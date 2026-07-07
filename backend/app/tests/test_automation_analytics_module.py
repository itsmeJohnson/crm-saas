import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.workflow import Workflow, WorkflowExecution
from app.models.queue import QueueJob
from app.models.rule import Rule, RuleEvaluation
from app.models.automation import AutomationJob, AutomationRun, SLAPolicy, SLABreach
from app.models.sla import SLATracker
from app.models.escalation import EscalationRule, EscalationEvent
from app.models.approval import ApprovalRequest
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


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "AA Org", "slug": "aa-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@aa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@aa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


async def _seed(db: AsyncSession, d: dict):
    org, admin = d["org"].id, d["admin"].id
    now = _now()
    # ---- workflow: 2 completed (one 2s, one 4s) + 1 failed ----
    wf = Workflow(organization_id=org, name="Lead welcome", status="published", trigger_event="lead_created",
                  entity_type="lead", graph={"nodes": [], "edges": []}, created_by=admin)
    db.add(wf); await db.flush()
    db.add(WorkflowExecution(organization_id=org, workflow_id=wf.id, trigger_event="lead_created", entity_type="lead",
                             status="completed", steps_run=2, started_at=now - timedelta(hours=1),
                             finished_at=now - timedelta(hours=1) + timedelta(seconds=2)))
    db.add(WorkflowExecution(organization_id=org, workflow_id=wf.id, trigger_event="lead_created", entity_type="lead",
                             status="completed", steps_run=3, started_at=now - timedelta(hours=2),
                             finished_at=now - timedelta(hours=2) + timedelta(seconds=4)))
    db.add(WorkflowExecution(organization_id=org, workflow_id=wf.id, trigger_event="lead_created", entity_type="lead",
                             status="failed", error="boom", started_at=now - timedelta(hours=3)))
    # a test execution must be EXCLUDED from analytics
    db.add(WorkflowExecution(organization_id=org, workflow_id=wf.id, trigger_event="lead_created", entity_type="lead",
                             status="completed", is_test=True, started_at=now - timedelta(hours=1)))
    # ---- queue: succeeded / failed / dead_letter ----
    for st, dur in [("succeeded", 120), ("succeeded", 80), ("failed", 50), ("dead_letter", None)]:
        db.add(QueueJob(organization_id=org, queue="email", job_type="send_email", status=st,
                        run_at=now, duration_ms=dur, created_by=admin))
    # ---- automation runs: success + failed ----
    db.add(AutomationRun(organization_id=org, job_key="sla_scan", status="success", triggered_by="schedule",
                         items_processed=5, duration_ms=200, started_at=now, finished_at=now))
    db.add(AutomationRun(organization_id=org, job_key="dunning", status="failed", triggered_by="schedule",
                         items_processed=0, started_at=now))
    db.add(AutomationJob(organization_id=org, job_key="sla_scan", name="SLA scan", is_enabled=True))
    # ---- rules + evaluations ----
    rule = Rule(organization_id=org, name="Hot", entity_type="lead", definition={"type": "group", "logic": "and", "children": []},
                priority=100, conflict_strategy="highest_priority", eval_count=2, match_count=1, created_by=admin)
    db.add(rule); await db.flush()
    db.add(RuleEvaluation(organization_id=org, rule_id=rule.id, entity_type="lead", matched=True, is_test=True))
    db.add(RuleEvaluation(organization_id=org, rule_id=rule.id, entity_type="lead", matched=False, is_test=True))
    # ---- SLA: 1 met + 1 breached tracker, 1 open breach ----
    pol = SLAPolicy(organization_id=org, name="Lead FR", entity_type="lead", metric="first_response",
                    threshold_hours=4, created_by=admin)
    db.add(pol); await db.flush()
    db.add(SLATracker(organization_id=org, policy_id=pol.id, entity_type="lead", entity_id=uuid.uuid4(),
                      status="met", started_at=now - timedelta(hours=5)))
    db.add(SLATracker(organization_id=org, policy_id=pol.id, entity_type="lead", entity_id=uuid.uuid4(),
                      status="breached", started_at=now - timedelta(hours=6)))
    db.add(SLABreach(organization_id=org, policy_id=pol.id, entity_type="lead", entity_id=uuid.uuid4(),
                     metric="first_response", hours_elapsed=8.0, resolved=False, breached_at=now))
    # ---- escalation: rule + 2 events (level 0 + 1) ----
    er = EscalationRule(organization_id=org, name="Idle leads", entity_type="lead", trigger_condition="no_activity",
                        levels=[{"after_hours": 24, "escalate_to": "manager"}], created_by=admin)
    db.add(er); await db.flush()
    db.add(EscalationEvent(organization_id=org, rule_id=er.id, entity_type="lead", entity_id=uuid.uuid4(),
                           level=0, escalate_to="manager", escalated_at=now))
    db.add(EscalationEvent(organization_id=org, rule_id=er.id, entity_type="task", entity_id=uuid.uuid4(),
                           level=1, escalate_to="department_head", escalated_at=now))
    # ---- approvals: approved / rejected / pending ----
    for st, dec in [("approved", now), ("rejected", now), ("pending", None)]:
        db.add(ApprovalRequest(organization_id=org, request_type="expense", title="T", current_level=1, total_levels=1,
                               status=st, requested_by=admin, created_by=admin,
                               created_at=now - timedelta(hours=2), decided_at=dec))
    await db.commit()


@pytest.mark.asyncio
async def test_overview_aggregates_all_subsystems_and_perms(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await _seed(db, d)
    # employees cannot see automation analytics
    assert (await client.get("/api/v1/automation-analytics/overview", headers=d["h_emp"])).status_code == 403
    ov = (await client.get("/api/v1/automation-analytics/overview", headers=d["h_admin"])).json()
    # workflow: 3 non-test runs (2 completed, 1 failed) → success 66.7, avg exec 3000ms
    assert ov["workflow"]["total_runs"] == 3 and ov["workflow"]["completed"] == 2 and ov["workflow"]["failed"] == 1
    assert ov["workflow"]["success_rate"] == 66.7
    assert ov["workflow"]["avg_execution_ms"] == 3000.0 and ov["workflow"]["max_execution_ms"] == 4000.0
    # queue: 4 jobs, 2 succeeded, avg duration over the 3 timed = (120+80+50)/3
    assert ov["queue"]["total"] == 4 and ov["queue"]["succeeded"] == 2 and ov["queue"]["dead_letter"] == 1
    assert ov["queue"]["avg_duration_ms"] == round((120 + 80 + 50) / 3, 1)
    # automation jobs, rules, sla, escalation, approval
    assert ov["automation_jobs"]["runs"] == 2 and ov["automation_jobs"]["items_processed"] == 5
    assert ov["rules"]["evaluations"] == 2 and ov["rules"]["matches"] == 1 and ov["rules"]["match_rate"] == 50.0
    assert ov["sla"]["tracked"] == 2 and ov["sla"]["breached"] == 1 and ov["sla"]["compliance_rate"] == 50.0 and ov["sla"]["open_breaches"] == 1
    assert ov["escalation"]["total"] == 2
    assert ov["approval"]["total"] == 3 and ov["approval"]["approved"] == 1 and ov["approval"]["approval_rate"] == 50.0
    assert "from" in ov and "to" in ov


@pytest.mark.asyncio
async def test_workflow_queue_rule_details(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await _seed(db, d)
    wf = (await client.get("/api/v1/automation-analytics/workflows", headers=d["h_admin"])).json()
    assert wf["success_rate"] == 66.7 and len(wf["failures"]) == 1 and wf["failures"][0]["error"] == "boom"
    assert wf["top_workflows"][0]["name"] == "Lead welcome" and wf["top_workflows"][0]["runs"] == 3
    q = (await client.get("/api/v1/automation-analytics/queue", headers=d["h_admin"])).json()
    assert any(r["queue"] == "email" for r in q["by_queue"]) and any(r["job_type"] == "send_email" for r in q["by_type"])
    ru = (await client.get("/api/v1/automation-analytics/rules", headers=d["h_admin"])).json()
    assert ru["top_rules"][0]["name"] == "Hot" and ru["top_rules"][0]["evaluations"] == 2


@pytest.mark.asyncio
async def test_top_sla_escalation_approval_and_dashboard(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await _seed(db, d)
    top = (await client.get("/api/v1/automation-analytics/top", headers=d["h_admin"])).json()
    kinds = {i["kind"] for i in top["items"]}
    assert "workflow" in kinds and "job" in kinds
    sla = (await client.get("/api/v1/automation-analytics/sla", headers=d["h_admin"])).json()
    assert sla["compliance_rate"] == 50.0 and sla["breaches_by_metric"].get("first_response") == 1
    esc = (await client.get("/api/v1/automation-analytics/escalation", headers=d["h_admin"])).json()
    assert esc["total"] == 2 and esc["by_entity"].get("lead") == 1 and "1" in esc["by_level"]
    appr = (await client.get("/api/v1/automation-analytics/approval", headers=d["h_admin"])).json()
    assert appr["by_type"].get("expense") == 3 and appr["avg_decision_hours"] is not None
    dash = (await client.get("/api/v1/automation-analytics/dashboard", headers=d["h_admin"])).json()
    assert dash["workflow_success_rate"] == 66.7 and dash["approvals_pending"] == 1 and dash["queue_failed"] == 2


@pytest.mark.asyncio
async def test_trend_export_and_filter(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await _seed(db, d)
    tr = (await client.get("/api/v1/automation-analytics/trend", params={"granularity": "daily"}, headers=d["h_admin"])).json()
    assert tr["granularity"] == "daily" and len(tr["series"]) >= 1
    assert sum(b["workflow_runs"] for b in tr["series"]) == 3
    # invalid granularity rejected
    assert (await client.get("/api/v1/automation-analytics/trend", params={"granularity": "yearly"}, headers=d["h_admin"])).status_code == 400
    # a date filter that predates all data yields empty/zeroed metrics
    past = (await client.get("/api/v1/automation-analytics/overview",
            params={"date_from": "2020-01-01", "date_to": "2020-01-31"}, headers=d["h_admin"])).json()
    assert past["workflow"]["total_runs"] == 0 and past["approval"]["total"] == 0
    # CSV export
    csv_resp = await client.get("/api/v1/automation-analytics/export", headers=d["h_admin"])
    assert csv_resp.status_code == 200 and "Automation analytics" in csv_resp.text and "Workflow" in csv_resp.text

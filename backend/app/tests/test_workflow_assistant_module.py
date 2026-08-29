import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.workflow import Workflow, WorkflowExecution
from app.models.queue import QueueJob
from app.models.audit_log import AuditLog
from app.services.workflow_assistant_service import parse_workflow_prompt
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "WA Org", "slug": "wa-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@wa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@wa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage)
        await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- NL parsing (pure) ----------
def test_parse_workflow_prompt_full_sentence():
    p = parse_workflow_prompt(
        "When a new lead comes in with value over 1,00,000 from source is referral, "
        "send an email saying 'Welcome aboard' and create a task to call them, then notify the manager")
    assert p["trigger_event"] == "lead_created"
    assert {"field": "value", "op": "gt", "value": 100000.0} in p["conditions"]
    actions = [a["action"] for a in p["actions"]]
    assert "send_email" in actions and "create_task" in actions and "create_notification" in actions
    email = next(a for a in p["actions"] if a["action"] == "send_email")
    assert email["message"] == "Welcome aboard"


def test_parse_workflow_prompt_defaults():
    p = parse_workflow_prompt("do something nice")
    assert p["trigger_event"] == "lead_created"
    assert p["actions"][0]["action"] == "create_notification"
    assert any("defaulted" in n.lower() for n in p["notes"])
    p2 = parse_workflow_prompt("when sla is breached assign and update status to Contacted")
    assert p2["trigger_event"] == "sla_breached"
    assert {"action": "update_status", "value": "Contacted"} in p2["actions"]


# ---------- generation ----------
@pytest.mark.asyncio
async def test_generate_preview_and_create(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/workflow-assistant/generate", headers=setup["h_admin"],
                          json={"prompt": "when a lead is converted create a task to start onboarding and notify"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trigger_event"] == "lead_converted" and body["created"] is None
    node_types = [n["type"] for n in body["graph"]["nodes"]]
    assert "trigger" in node_types and "action" in node_types and "end" in node_types

    r = await client.post("/api/v1/workflow-assistant/generate", headers=setup["h_admin"],
                          json={"prompt": "when a new lead arrives send an email", "create": True,
                                "name": "Auto welcome"})
    assert r.status_code == 200
    created = r.json()["created"]
    assert created and created["status"] == "draft"
    w = (await db.execute(select(Workflow).filter(
        Workflow.organization_id == setup["org"].id, Workflow.name == "Auto welcome"))).scalars().first()
    assert w is not None and w.is_enabled is False
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "WORKFLOW_GENERATED"))).scalars().all()
    assert len(audits) == 1
    # employees cannot generate
    r = await client.post("/api/v1/workflow-assistant/generate", headers=setup["h_emp"],
                          json={"prompt": "when a new lead arrives send an email"})
    assert r.status_code == 403


# ---------- suggestions ----------
@pytest.mark.asyncio
async def test_workflow_suggestions_evidence(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"]
    old = _now() - timedelta(days=10)
    for i in range(3):
        lead = Lead(organization_id=org.id, first_name=f"L{i}", last_name="X", title="t",
                    status="New", value=1000, created_by=setup["admin"].id,
                    stage_id=setup["stage"].id)
        db.add(lead)
    await db.commit()
    # backdate updated_at so they read as stale
    for l in (await db.execute(select(Lead).filter(Lead.organization_id == org.id))).scalars().all():
        l.updated_at = old
    await db.commit()

    r = await client.get("/api/v1/workflow-assistant/suggestions", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"] for s in body["suggestions"]}
    assert "auto_assign_leads" in keys and "stale_lead_followup" in keys and "welcome_new_lead" in keys
    assert body["signals"]["unassigned_leads"] == 3 and body["signals"]["stale_leads"] == 3
    auto = next(s for s in body["suggestions"] if s["key"] == "auto_assign_leads")
    assert auto["already_covered"] is False and auto["draft_graph"]["nodes"]
    assert (await client.get("/api/v1/workflow-assistant/suggestions",
                             headers=setup["h_emp"])).status_code == 403


# ---------- rule recommendations ----------
@pytest.mark.asyncio
async def test_rule_recommendations(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"]
    for i in range(6):
        db.add(Lead(organization_id=org.id, first_name=f"R{i}", last_name="Y", title="t",
                    source="Referral", status="Converted" if i < 3 else "New",
                    value=1000, created_by=setup["admin"].id, stage_id=setup["stage"].id))
    db.add(Lead(organization_id=org.id, first_name="Big", last_name="Fish", title="t",
                status="New", value=90000, created_by=setup["admin"].id,
                stage_id=setup["stage"].id))
    await db.commit()
    r = await client.get("/api/v1/workflow-assistant/rule-recommendations", headers=setup["h_admin"])
    assert r.status_code == 200
    recs = {x["key"]: x for x in r.json()["recommendations"]}
    assert "score_top_source" in recs and "Referral" in recs["score_top_source"]["title"]
    assert recs["score_top_source"]["rule_definition"]["children"][0]["value"] == "Referral"
    assert "assign_high_value" in recs


# ---------- bottlenecks ----------
@pytest.mark.asyncio
async def test_bottleneck_detection(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"]
    w = Workflow(organization_id=org.id, name="Flaky flow", status="published", version=1,
                 is_enabled=True, trigger_event="lead_created", entity_type="lead",
                 graph={"nodes": [{"id": "t1", "type": "trigger", "config": {}}], "edges": []},
                 created_by=setup["admin"].id)
    db.add(w)
    await db.flush()
    for i in range(6):
        db.add(WorkflowExecution(organization_id=org.id, workflow_id=w.id, version=1,
                                 trigger_event="lead_created", entity_type="lead",
                                 status="failed" if i < 3 else "completed", is_test=False,
                                 error="boom" if i < 3 else None,
                                 started_at=_now() - timedelta(days=1),
                                 finished_at=_now() - timedelta(days=1) + timedelta(seconds=2)))
    db.add(QueueJob(organization_id=org.id, queue="default", job_type="ai_task",
                    status="dead_letter", run_at=_now()))
    await db.commit()

    r = await client.get("/api/v1/workflow-assistant/bottlenecks", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    areas = {b["area"] for b in body["bottlenecks"]}
    assert "workflow" in areas and "queue" in areas
    flaky = next(b for b in body["bottlenecks"] if b["area"] == "workflow")
    assert "Flaky flow" in flaky["title"] and "50.0%" in flaky["evidence"]
    assert body["bottlenecks"][0]["severity"] == "high"  # severity-sorted


# ---------- optimizations ----------
@pytest.mark.asyncio
async def test_optimization_hygiene(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"]
    db.add(Workflow(organization_id=org.id, name="Dormant", status="published", version=1,
                    is_enabled=False, trigger_event="lead_created", entity_type="lead",
                    graph={"nodes": [], "edges": []}, created_by=setup["admin"].id))
    db.add(Workflow(organization_id=org.id, name="Silent", status="published", version=1,
                    is_enabled=True, trigger_event="task_completed", entity_type="task",
                    graph={"nodes": [{"id": "t1", "type": "trigger", "config": {}}], "edges": []},
                    created_by=setup["admin"].id))
    await db.commit()
    r = await client.get("/api/v1/workflow-assistant/optimizations", headers=setup["h_admin"])
    kinds = {(o["workflow"], o["kind"]) for o in r.json()["optimizations"]}
    assert ("Dormant", "disabled_published") in kinds
    assert ("Silent", "never_ran") in kinds
    assert ("Silent", "no_actions") in kinds


# ---------- validation + simulation ----------
@pytest.mark.asyncio
async def test_validate_and_simulate(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/workflow-assistant/generate", headers=setup["h_admin"],
                          json={"prompt": "when a new lead arrives send an sms", "create": True,
                                "name": "Lint me"})
    wid = r.json()["created"]["id"]
    # sabotage: add an unreachable node + an unconfigured email action
    w = (await db.execute(select(Workflow).filter(Workflow.id == uuid.UUID(wid)))).scalars().first()
    graph = dict(w.graph)
    graph["nodes"] = graph["nodes"] + [
        {"id": "island", "type": "action", "config": {"action": "send_email"}}]
    w.graph = graph
    await db.commit()

    r = await client.get(f"/api/v1/workflow-assistant/workflows/{wid}/validate", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True  # structurally fine, only warnings
    warns = " ".join(body["warnings"])
    assert "island" in warns and "no message" in warns and "not published" in warns
    assert body["health_score"] < 100

    r = await client.post(f"/api/v1/workflow-assistant/workflows/{wid}/simulate", headers=setup["h_admin"])
    assert r.status_code == 200
    sim = r.json()
    assert sim.get("is_test") is True or sim.get("status") == "test"


# ---------- insights + report + export ----------
@pytest.mark.asyncio
async def test_insights_report_export(client: AsyncClient, setup, db: AsyncSession):
    org = setup["org"]
    w = Workflow(organization_id=org.id, name="Busy flow", status="published", version=1,
                 is_enabled=True, trigger_event="lead_created", entity_type="lead",
                 graph={"nodes": [{"id": "t1", "type": "trigger", "config": {}}], "edges": []},
                 created_by=setup["admin"].id)
    db.add(w)
    await db.flush()
    for i in range(4):
        db.add(WorkflowExecution(organization_id=org.id, workflow_id=w.id, version=1,
                                 trigger_event="lead_created", entity_type="lead",
                                 status="completed" if i else "failed", is_test=False,
                                 started_at=_now() - timedelta(hours=i),
                                 finished_at=_now() - timedelta(hours=i) + timedelta(seconds=1)))
    await db.commit()

    r = await client.get("/api/v1/workflow-assistant/insights", headers=setup["h_admin"])
    body = r.json()
    assert body["totals"]["runs"] == 4 and body["totals"]["success_rate"] == 75.0
    row = body["workflows"][0]
    assert row["workflow"] == "Busy flow" and row["runs_30d"] == 4 and row["avg_duration_s"] == 1.0
    assert body["trend"]

    rep = (await client.get("/api/v1/workflow-assistant/report", headers=setup["h_admin"])).json()
    assert rep["summary"]["runs_30d"] == 4 and "suggestions" in rep and "bottlenecks" in rep

    assert (await client.get("/api/v1/workflow-assistant/export",
                             headers=setup["h_emp"])).status_code == 403
    r = await client.get("/api/v1/workflow-assistant/export", headers=setup["h_admin"])
    assert r.status_code == 200 and "Busy flow" in r.text
    audits = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == org.id,
        AuditLog.action == "WORKFLOW_ASSISTANT_EXPORTED"))).scalars().all()
    assert len(audits) == 1

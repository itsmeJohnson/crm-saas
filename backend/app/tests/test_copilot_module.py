import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.activity import Activity
from app.models.company import Company
from app.models.task import Task
from app.models.calendar_event import CalendarEvent
from app.models.audit_log import AuditLog
from app.services.copilot_service import CopilotService, _parse_when
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


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Copilot Org", "slug": "copilot-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@cp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@cp.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    ada = Lead(organization_id=org.id, first_name="Ada", last_name="Lovelace", title="t", status="Qualified",
               value=9000, score=80, priority="High", email="ada@x.com", phone="+911234500000", city="Mumbai",
               company_name="Analytical", assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add(ada)
    db.add(Lead(organization_id=org.id, last_name="Babbage", title="t", status="New", value=500, score=20,
                priority="Low", city="Pune", assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    db.add(Lead(organization_id=org.id, last_name="Turing", title="t", status="Converted", value=5000,
                converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    db.add(Company(organization_id=org.id, name="Acme Retail", industry="Retail", company_type="Customer",
                   created_by=admin.id))
    await db.flush()
    db.add(Activity(organization_id=org.id, activity_type="Call", subject="Intro call", lead_id=ada.id,
                    assigned_user_id=admin.id, created_by=admin.id, call_direction="OUTBOUND"))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "ada": ada,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def test_intent_parser():
    svc = CopilotService.__new__(CopilotService)
    assert svc.parse_intent("find leads in Mumbai")["intent"] == "search"
    assert svc.parse_intent("how many open leads do I have")["intent"] == "question"
    assert svc.parse_intent("draft an email to Ada about a demo") == {
        "intent": "draft", "channel": "email", "target": "Ada", "goal": "a demo"}
    assert svc.parse_intent("draft a whatsapp to John")["channel"] == "whatsapp"
    assert svc.parse_intent("send an sms")["intent"] != "draft"  # no draft verb
    assert svc.parse_intent("create a task follow up")["intent"] == "create_task"
    assert svc.parse_intent("schedule a meeting with Ada tomorrow")["intent"] == "schedule_meeting"
    assert svc.parse_intent("find opportunities")["intent"] == "opportunities"
    assert svc.parse_intent("summarize lead Ada")["intent"] == "summarize"
    assert svc.parse_intent("generate a report of leads by status")["intent"] == "report"
    assert svc.parse_intent("tell me a joke")["intent"] == "chat"


def test_parse_when():
    assert _parse_when("no time here") is None
    tm = _parse_when("tomorrow at 3pm")
    assert tm is not None and tm.hour == 15


@pytest.mark.asyncio
async def test_capabilities(client: AsyncClient, setup):
    r = await client.get("/api/v1/copilot/capabilities", headers=setup["h_admin"])
    body = r.json()
    assert body["voice_ready"] is True
    intents = {c["intent"] for c in body["capabilities"]}
    assert {"search", "question", "report", "summarize", "opportunities", "draft",
            "create_task", "schedule_meeting"} <= intents


@pytest.mark.asyncio
async def test_search_with_filters(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "find leads in Mumbai"})
    body = r.json()
    assert body["intent"] == "search"
    names = [x["name"] for x in body["data"]["results"]]
    assert "Ada Lovelace" in names and all(x["city"] == "Mumbai" for x in body["data"]["results"])
    assert body["speech"]  # voice-ready
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "show high priority leads"})
    assert all(x["score"] >= 0 for x in r.json()["data"]["results"])
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "list customers"})
    assert r.json()["data"]["results"][0]["name"] == "Acme Retail"


@pytest.mark.asyncio
async def test_questions(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "how many leads do I have"})
    assert r.json()["data"]["total"] == 3 and r.json()["data"]["converted"] == 1
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "what is my conversion rate"})
    assert r.json()["data"]["conversion_rate"] == round(1 * 100 / 3, 1)
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "what's my pipeline value"})
    assert r.json()["data"]["pipeline_value"] == 9500  # Ada 9000 + Babbage 500 (Turing converted)


@pytest.mark.asyncio
async def test_summarize_record_and_activity(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "summarize lead Ada Lovelace"})
    body = r.json()
    assert body["intent"] == "summarize" and body["data"]["name"] == "Ada Lovelace"
    assert "Summarize this lead" in body["reply"]  # mock echoes rendered prompt
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "summarize recent activity"})
    assert r.json()["intent"] == "summarize" and r.json()["data"]["activities"] >= 1
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "summarize lead Nonexistent Person"})
    assert "couldn't find" in r.json()["reply"]


@pytest.mark.asyncio
async def test_opportunities(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "find opportunities"})
    body = r.json()
    assert body["intent"] == "opportunities"
    assert len(body["data"]["hot_leads"]) >= 1
    assert "Ada" in body["reply"]


@pytest.mark.asyncio
async def test_report_generation(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "generate a report of leads by status"})
    body = r.json()
    assert body["intent"] == "report"
    assert body["data"]["chart"]["group"] == "status"
    assert len(body["data"]["rows"]) >= 1


@pytest.mark.asyncio
async def test_draft_email_proposes_action(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "draft an email to Ada about a demo"})
    body = r.json()
    assert body["intent"] == "draft" and body["requires_confirmation"] is True
    action = body["pending_action"]
    assert action["type"] == "send_email" and action["context_type"] == "lead"
    assert body["data"]["channel"] == "email" and body["data"]["draft"]
    # whatsapp draft
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "draft a whatsapp to Ada about pricing"})
    assert r.json()["pending_action"]["type"] == "send_whatsapp"


@pytest.mark.asyncio
async def test_create_task_flow(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "create a task call Ada tomorrow"})
    body = r.json()
    assert body["intent"] == "create_task" and body["requires_confirmation"] is True
    action = body["pending_action"]
    assert action["type"] == "create_task" and action["due_date"] is not None
    r = await client.post("/api/v1/copilot/execute", headers=setup["h_admin"], json={"action": action})
    assert r.json()["status"] == "done" and r.json()["result"]["created"] == "task"
    tasks = (await db.execute(select(Task).filter(Task.organization_id == setup["org"].id))).scalars().all()
    assert len(tasks) == 1 and "call ada" in tasks[0].title.lower()
    audit = (await db.execute(select(AuditLog).filter(
        AuditLog.organization_id == setup["org"].id,
        AuditLog.action == "COPILOT_ACTION_EXECUTED"))).scalars().all()
    assert len(audit) == 1


@pytest.mark.asyncio
async def test_schedule_meeting_flow(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "schedule a meeting with Ada tomorrow at 2pm"})
    body = r.json()
    assert body["intent"] == "schedule_meeting"
    action = body["pending_action"]
    assert action["type"] == "schedule_meeting" and action.get("lead_id") == str(setup["ada"].id)
    r = await client.post("/api/v1/copilot/execute", headers=setup["h_admin"], json={"action": action})
    assert r.json()["result"]["created"] == "calendar_event"
    events = (await db.execute(select(CalendarEvent).filter(
        CalendarEvent.organization_id == setup["org"].id))).scalars().all()
    assert len(events) == 1 and "Ada" in events[0].title


@pytest.mark.asyncio
async def test_send_message_action(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/copilot/execute", headers=setup["h_admin"], json={"action": {
        "type": "send_sms", "context_type": "lead", "context_id": str(setup["ada"].id),
        "body": "Hi Ada, following up."}})
    assert r.json()["status"] == "done" and r.json()["result"]["sent"] == "sms"


@pytest.mark.asyncio
async def test_conversation_history(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "how many leads do I have"})
    convo_id = r.json()["conversation_id"]
    assert convo_id
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"],
                          json={"message": "find leads in Pune", "conversation_id": convo_id})
    assert r.json()["conversation_id"] == convo_id
    r = await client.get(f"/api/v1/copilot/conversations/{convo_id}/messages", headers=setup["h_admin"])
    msgs = r.json()
    # 2 user turns + 2 assistant replies persisted
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    r = await client.get("/api/v1/copilot/conversations", headers=setup["h_admin"])
    assert any(c["id"] == convo_id for c in r.json())


@pytest.mark.asyncio
async def test_employee_scope(client: AsyncClient, setup, db: AsyncSession):
    # a lead owned by someone outside the employee's downline is invisible to them
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_emp"],
                          json={"message": "how many leads do I have"})
    assert r.json()["data"]["total"] == 0  # all seeded leads belong to admin
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_emp"],
                          json={"message": "find leads in Mumbai"})
    assert r.json()["data"]["results"] == []


@pytest.mark.asyncio
async def test_validation(client: AsyncClient, setup):
    r = await client.post("/api/v1/copilot/ask", headers=setup["h_admin"], json={"message": "   "})
    assert r.status_code == 400
    r = await client.post("/api/v1/copilot/execute", headers=setup["h_admin"],
                          json={"action": {"type": "delete_everything"}})
    assert r.status_code == 400

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
from app.services.comm_intelligence_service import (
    analyze_sentiment, detect_intents, extract_action_items, detect_language, follow_up_suggestions)
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


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "CI Org", "slug": "ci-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@ci.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@ci.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    lead = Lead(organization_id=org.id, first_name="Ada", last_name="Lovelace", title="t", status="Qualified",
                assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id)
    db.add(lead)
    await db.flush()
    now = datetime.now(timezone.utc)
    # positive call w/ pricing intent + action item
    db.add(Activity(organization_id=org.id, activity_type="Call", subject="Great discovery call",
                    description="The client is very interested and happy. What is the price? I will send a quote tomorrow.",
                    lead_id=lead.id, assigned_user_id=admin.id, created_by=admin.id,
                    call_direction="OUTBOUND", call_duration=600, created_at=now - timedelta(days=2)))
    # negative complaint email
    db.add(Activity(organization_id=org.id, activity_type="Email", subject="Complaint about delay",
                    description="I am very disappointed and unhappy. This is unacceptable. Please cancel my order.",
                    lead_id=lead.id, assigned_user_id=admin.id, created_by=admin.id,
                    call_direction="INBOUND", created_at=now - timedelta(days=1)))
    # employee-owned SMS (scope test)
    db.add(Activity(organization_id=org.id, activity_type="SMS", subject="SMS", description="ok thanks",
                    assigned_user_id=emp.id, created_by=emp.id, call_direction="INBOUND"))
    await db.commit()
    calls = (await db.execute(select(Activity).filter(Activity.organization_id == org.id,
             Activity.activity_type == "Call"))).scalars().first()
    return {"org": org, "admin": admin, "emp": emp, "lead": lead, "call": calls,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


# ---------- deterministic NLP unit tests ----------
def test_sentiment():
    assert analyze_sentiment("This is great, I am very happy and interested")["label"] == "positive"
    assert analyze_sentiment("terrible, disappointed and angry, this is a problem")["label"] == "negative"
    assert analyze_sentiment("the meeting is at 3pm")["label"] == "neutral"


def test_intents():
    assert "pricing" in detect_intents("what is the price and cost?")
    assert "scheduling" in detect_intents("can we schedule a meeting next week")
    assert "complaint" in detect_intents("I have an issue, this is broken")
    assert "question" in detect_intents("how does this work?")


def test_action_items():
    items = extract_action_items("I will send the quote. Please review it. The weather is nice.")
    assert any("send the quote" in i.lower() for i in items)
    assert any("please review" in i.lower() for i in items)
    assert not any("weather" in i.lower() for i in items)


def test_language_detection():
    assert detect_language("hello, what is the price")["code"] == "en"
    assert detect_language("नमस्ते आप कैसे हैं")["code"] == "hi"  # Devanagari
    assert detect_language("hola gracias por favor quiero")["code"] == "es"


def test_follow_up_suggestions():
    s = follow_up_suggestions(["pricing"], {"label": "positive"}, [])
    assert any("pricing" in x.lower() or "quote" in x.lower() for x in s)
    s = follow_up_suggestions([], {"label": "negative"}, [])
    assert any("concern" in x.lower() for x in s)


# ---------- API tests ----------
@pytest.mark.asyncio
async def test_analyze_endpoint(client: AsyncClient, setup):
    r = await client.post("/api/v1/comm-intelligence/analyze", headers=setup["h_admin"],
                          json={"text": "I love this, what is the pricing? Please send a quote."})
    b = r.json()
    assert b["sentiment"]["label"] == "positive"
    assert "pricing" in b["intents"] and b["primary_intent"] in ("pricing", "question", "interest")
    assert b["action_items"] and b["follow_up_suggestions"]
    assert b["language"]["code"] == "en"
    bad = await client.post("/api/v1/comm-intelligence/analyze", headers=setup["h_admin"], json={"text": "  "})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_activity_intelligence_and_summary(client: AsyncClient, setup):
    r = await client.get(f"/api/v1/comm-intelligence/activities/{setup['call'].id}", headers=setup["h_admin"])
    b = r.json()
    assert b["channel"] == "Call" and b["duration"] == 600
    assert b["sentiment"]["label"] == "positive" and "pricing" in b["intents"]
    assert any("send a quote" in i.lower() for i in b["action_items"])
    # AI summary via gateway (mock echoes the rendered prompt)
    r = await client.get(f"/api/v1/comm-intelligence/activities/{setup['call'].id}/summary", headers=setup["h_admin"])
    assert r.status_code == 200 and "Summarize the following" in r.json()["text"]


@pytest.mark.asyncio
async def test_transcript_support(client: AsyncClient, setup):
    r = await client.post("/api/v1/comm-intelligence/transcript", headers=setup["h_admin"], json={
        "transcript": "Agent: Hello. Customer: I am interested in a demo. Agent: I will schedule it and send details.",
        "activity_id": str(setup["call"].id)})
    b = r.json()
    assert b["source"] == "transcript" and b["sentiment"]["label"] in ("positive", "neutral")
    assert "interest" in b["intents"] or "scheduling" in b["intents"]
    assert b["action_items"] and b["activity_id"] == str(setup["call"].id)


@pytest.mark.asyncio
async def test_translate_ready(client: AsyncClient, setup):
    r = await client.post("/api/v1/comm-intelligence/translate", headers=setup["h_admin"],
                          json={"text": "hola gracias", "target_lang": "en"})
    b = r.json()
    assert b["source_language"]["code"] == "es" and b["target_lang"] == "en"
    assert "Translate the following" in b["translation"]  # mock echoes prompt


@pytest.mark.asyncio
async def test_conversation_analysis(client: AsyncClient, setup):
    r = await client.get("/api/v1/comm-intelligence/conversation", headers=setup["h_admin"],
                         params={"lead_id": str(setup["lead"].id)})
    b = r.json()
    assert b["messages"] == 2  # call + email on this lead
    assert len(b["timeline"]) == 2
    # sentiment went positive → negative
    assert b["sentiment_trend"] == "declining" and b["overall_sentiment"] in ("neutral", "negative")
    assert b["action_items"] and b["follow_up_suggestions"]
    intents = {i["intent"] for i in b["intents"]}
    assert "pricing" in intents or "complaint" in intents


@pytest.mark.asyncio
async def test_meeting_summary(client: AsyncClient, setup):
    r = await client.post("/api/v1/comm-intelligence/meeting-summary", headers=setup["h_admin"], json={
        "notes": "We agreed on the scope. I will send the contract. The client will review by Friday."})
    b = r.json()
    assert "Summarize the following" in b["summary"]  # gateway
    assert any("send the contract" in i.lower() for i in b["action_items"])


@pytest.mark.asyncio
async def test_dashboard_and_report(client: AsyncClient, setup):
    r = await client.get("/api/v1/comm-intelligence/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["total"] == 3  # call + email + sms (admin privileged sees all)
    assert d["sentiment"]["positive"] >= 1 and d["sentiment"]["negative"] >= 1
    assert d["action_items"] >= 1 and d["by_channel"].get("Call") == 1
    r = await client.get("/api/v1/comm-intelligence/report", headers=setup["h_admin"])
    assert r.json()["total"] == 3
    r = await client.get("/api/v1/comm-intelligence/export", headers=setup["h_admin"])
    lines = r.text.strip().splitlines()
    assert lines[0] == "channel,sentiment,primary_intent,action_items,language" and len(lines) == 4


@pytest.mark.asyncio
async def test_scope(client: AsyncClient, setup):
    # employee sees only their own SMS
    r = await client.get("/api/v1/comm-intelligence/dashboard", headers=setup["h_emp"])
    assert r.json()["total"] == 1
    # and cannot open the admin's call
    r = await client.get(f"/api/v1/comm-intelligence/activities/{setup['call'].id}", headers=setup["h_emp"])
    assert r.status_code == 404

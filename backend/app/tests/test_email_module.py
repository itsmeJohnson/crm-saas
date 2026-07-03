import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.pipeline import PipelineStage
from app.models.notification import Notification
from app.models.email_settings import EmailSettings
from app.models.workflow_rule import WorkflowRule
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
        return ["EMAIL_MESSAGING", "LEAD_MANAGEMENT"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Email Org", "slug": "email-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@email.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await user_repo.create_user(org.id, {
        "email": "mgr@email.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Mgr", "last_name": "One", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@email.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
    await db.commit()

    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()

    lead = Lead(organization_id=org.id, first_name="Cust", last_name="Omer", email="cust@buyer.com",
                phone="+910000000001", title="Email Lead", status="New", assigned_user_id=emp.id,
                created_by=admin.id, stage_id=stage.id)
    db.add(lead)
    await db.commit()

    return {
        "org": org, "admin": admin, "mgr": mgr, "emp": emp, "lead": lead,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _enable_tracking(db, org_id):
    s = (await db.execute(select(EmailSettings).filter(EmailSettings.organization_id == org_id))).scalars().first()
    s.tracking_enabled = True
    s.tracking_base_url = "https://crm.example.com"
    db.add(s)
    await db.commit()
    return s


@pytest.mark.asyncio
async def test_settings_and_permissions(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/email/settings", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock"
    assert "smtp_password" not in body and "imap_password" not in body

    assert (await client.get("/api/v1/email/settings", headers=data["h_emp"])).status_code == 403
    r = await client.put("/api/v1/email/settings", json={
        "smtp_host": "smtp.test.com", "smtp_port": 587, "from_name": "Sales", "tracking_base_url": "https://x.io"},
        headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["smtp_host"] == "smtp.test.com"
    assert (await client.put("/api/v1/email/settings", json={"smtp_host": "x"}, headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_send_injects_tracking(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    await _enable_tracking(db, data["org"].id)

    r = await client.post("/api/v1/email/send", json={
        "subject": "Hello", "body": '<p>Hi <a href="https://site.com/x">link</a></p>',
        "lead_id": str(data["lead"].id)}, headers=data["h_emp"])
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["direction"] == "OUTBOUND"
    assert item["status"] == "sent"
    assert item["email_to"] == "cust@buyer.com"  # derived from lead
    assert item["thread_id"]

    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(item["id"])))).scalars().first()
    # body stored is the raw body; tracking is injected into the transmitted HTML only,
    # but the tracking id is persisted for pixel/click correlation
    assert act.email_tracking_id
    assert act.email_message_id


@pytest.mark.asyncio
async def test_open_and_click_tracking(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    await _enable_tracking(db, data["org"].id)
    send = await client.post("/api/v1/email/send", json={
        "subject": "Track", "body": '<a href="https://dest.com/p">go</a>', "to": "x@y.com"}, headers=data["h_admin"])
    aid = send.json()["id"]
    tid = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(aid)))).scalars().first().email_tracking_id

    # open pixel returns a gif and records the open
    r = await client.get(f"/api/v1/email/track/open/{tid}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/gif"

    # click redirects to the original url and records the click
    r = await client.get(f"/api/v1/email/track/click/{tid}", params={"u": "https://dest.com/p"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://dest.com/p"

    act = (await db.execute(select(Activity).filter(Activity.id == uuid.UUID(aid)))).scalars().first()
    await db.refresh(act)
    assert act.email_open_count >= 1
    assert act.email_click_count == 1
    assert act.email_opened_at is not None


@pytest.mark.asyncio
async def test_reply_threads(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    send = await client.post("/api/v1/email/send", json={
        "subject": "Quote", "body": "here", "to": "cust@buyer.com", "lead_id": str(data["lead"].id)},
        headers=data["h_emp"])
    orig = send.json()
    r = await client.post(f"/api/v1/email/{orig['id']}/reply", json={"body": "following up"}, headers=data["h_emp"])
    assert r.status_code == 201, r.text
    reply = r.json()
    assert reply["subject"].startswith("Re: ")
    assert reply["thread_id"] == orig["thread_id"]  # same thread

    # thread detail returns both messages
    r = await client.get(f"/api/v1/email/threads/{orig['thread_id']}", headers=data["h_emp"])
    assert r.status_code == 200
    assert len(r.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_forward(client: AsyncClient, setup: dict):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    send = await client.post("/api/v1/email/send", json={"subject": "Doc", "body": "body", "to": "a@b.com"},
                             headers=data["h_admin"])
    r = await client.post(f"/api/v1/email/{send.json()['id']}/forward", json={"to": "third@party.com", "body": "fyi"},
                          headers=data["h_admin"])
    assert r.status_code == 201, r.text
    assert r.json()["subject"].startswith("Fwd: ")
    assert r.json()["email_to"] == "third@party.com"


@pytest.mark.asyncio
async def test_drafts_lifecycle(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    # create draft
    r = await client.post("/api/v1/email/drafts", json={"subject": "WIP", "body": "draft body", "to": "d@e.com"},
                          headers=data["h_emp"])
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert r.json()["is_draft"] is True

    # appears in drafts folder, not sent
    drafts = await client.get("/api/v1/email/messages", params={"folder": "drafts"}, headers=data["h_emp"])
    assert any(m["id"] == did for m in drafts.json()["items"])

    # edit
    r = await client.patch(f"/api/v1/email/drafts/{did}", json={"body": "edited"}, headers=data["h_emp"])
    assert r.json()["body"] == "edited"

    # send it → no longer a draft, shows in sent
    r = await client.post(f"/api/v1/email/drafts/{did}/send", headers=data["h_emp"])
    assert r.status_code == 200, r.text
    assert r.json()["is_draft"] is False
    assert r.json()["status"] == "sent"
    sent = await client.get("/api/v1/email/messages", params={"folder": "sent"}, headers=data["h_emp"])
    assert any(m["id"] == did for m in sent.json()["items"])
    drafts = await client.get("/api/v1/email/messages", params={"folder": "drafts"}, headers=data["h_emp"])
    assert not any(m["id"] == did for m in drafts.json()["items"])


@pytest.mark.asyncio
async def test_inbound_ingest_matches_notifies_and_workflow(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    db.add(WorkflowRule(organization_id=data["org"].id, name="Email priority", trigger_event="email_received",
                        is_active=True, conditions=[], actions=[{"type": "set_priority", "value": "Urgent"}],
                        created_by=data["admin"].id))
    await db.commit()

    # drive the fetcher with a fake inbound from the lead's email
    from app.services import email_service_module as mod
    from app.services.email_providers import FetchedEmail

    class FakeFetcher:
        name = "mock"
        def fetch(self, *, limit=25):
            return [FetchedEmail(from_addr="cust@buyer.com", to_addr="sales@us.com",
                                 subject="Re: Quote", body="Interested", message_id="<in-1@buyer>", in_reply_to=None)]

    monkeypatch.setattr(mod, "get_fetcher", lambda s: FakeFetcher())

    r = await client.post("/api/v1/email/sync", headers=data["h_admin"])
    assert r.status_code == 200, r.text
    assert r.json()["ingested"] == 1

    inbound = (await db.execute(select(Activity).filter(
        Activity.organization_id == data["org"].id, Activity.activity_type == "Email",
        Activity.call_direction == "INBOUND"))).scalars().first()
    assert inbound is not None
    assert inbound.lead_id == data["lead"].id
    assert inbound.email_status == "received"

    notif = (await db.execute(select(Notification).filter(
        Notification.user_id == data["emp"].id, Notification.category == "email"))).scalars().first()
    assert notif is not None

    await db.refresh(data["lead"])
    assert data["lead"].priority == "Urgent"

    # a second sync with the same message id must not duplicate
    r = await client.post("/api/v1/email/sync", headers=data["h_admin"])
    assert r.json()["ingested"] == 0


@pytest.mark.asyncio
async def test_reports_and_scoping(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.get("/api/v1/email/settings", headers=data["h_admin"])
    await _enable_tracking(db, data["org"].id)
    send = await client.post("/api/v1/email/send", json={"subject": "A", "body": "b", "to": "z@z.com"},
                             headers=data["h_emp"])
    tid = (await db.execute(select(Activity).filter(
        Activity.id == uuid.UUID(send.json()["id"])))).scalars().first().email_tracking_id
    await client.get(f"/api/v1/email/track/open/{tid}")
    # admin also sends one
    await client.post("/api/v1/email/send", json={"subject": "C", "body": "d", "to": "w@w.com"}, headers=data["h_admin"])

    # employee sees only own in reports
    r = await client.get("/api/v1/email/reports", headers=data["h_emp"])
    assert r.json()["sent"] == 1
    assert r.json()["opened"] == 1
    assert r.json()["open_rate"] == 100.0
    # admin (privileged) sees both
    r = await client.get("/api/v1/email/reports", headers=data["h_admin"])
    assert r.json()["sent"] == 2


@pytest.mark.asyncio
async def test_workflow_crud_accepts_email_trigger_and_action(client: AsyncClient, setup: dict):
    data = setup
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "Email reply", "trigger_event": "email_received",
        "conditions": [], "actions": [{"type": "send_email", "subject": "Thanks", "message": "Got your email!"}]},
        headers=data["h_admin"])
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/leads/workflows", json={
        "name": "bad", "trigger_event": "email_bounced", "conditions": [], "actions": []},
        headers=data["h_admin"])
    assert r.status_code == 400

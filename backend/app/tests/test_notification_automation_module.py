import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.notification import Notification, NotificationPreference
from app.models.notification_automation import (
    NotificationRule, NotificationDelivery, NotificationDigestItem,
)
from app.models.queue import QueueJob
from app.services.notification_automation_service import NotificationAutomationService
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
    org = await OrganizationRepository(db).create({"name": "NA Org", "slug": "na-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@na.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@na.com", "hashed_password": get_password_hash("password123"),
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


async def _count_notifs(db, org_id, user_id, category=None):
    q = select(Notification).filter(Notification.organization_id == org_id, Notification.user_id == user_id)
    if category:
        q = q.filter(Notification.category == category)
    return (await db.execute(q)).scalars().all()


@pytest.mark.asyncio
async def test_catalog_crud_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/notification-automation/catalog", headers=d["h_admin"])).json()
    assert "owner" in cat["recipient_types"] and "in_app" in cat["channels"] and "*" in cat["trigger_events"]
    # employee cannot create
    assert (await client.post("/api/v1/notification-automation/rules", json={"name": "x", "trigger_event": "lead.created"}, headers=d["h_emp"])).status_code == 403
    # invalid recipient type rejected
    bad = await client.post("/api/v1/notification-automation/rules", json={
        "name": "x", "trigger_event": "lead.created", "recipients": [{"type": "nope"}]}, headers=d["h_admin"])
    assert bad.status_code == 400
    # valid create
    r = (await client.post("/api/v1/notification-automation/rules", json={
        "name": "Notify owner", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "creator"}], "channels": ["in_app"], "title": "New lead {{title}}"}, headers=d["h_admin"])).json()
    assert r["trigger_event"] == "lead.created" and r["channels"] == ["in_app"]


@pytest.mark.asyncio
async def test_event_fires_rule_and_creates_notification(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/notification-automation/rules", json={
        "name": "New lead", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "creator"}], "channels": ["in_app"],
        "title": "New lead: {{title}}", "body": "Status {{status}}", "category": "lead"}, headers=d["h_admin"])
    # creating a lead publishes lead.created → the rule fires → admin (creator) notified
    lead = (await client.post("/api/v1/leads/", json={"last_name": "Ping", "title": "Big Deal"}, headers=d["h_admin"])).json()
    notifs = await _count_notifs(db, d["org"].id, d["admin"].id, "lead")
    assert any("Big Deal" in n.title for n in notifs)  # {{title}} rendered
    # a delivery record was tracked
    dels = (await db.execute(select(NotificationDelivery).filter(
        NotificationDelivery.organization_id == d["org"].id, NotificationDelivery.channel == "in_app"))).scalars().all()
    assert len(dels) >= 1 and dels[0].status == "sent"


@pytest.mark.asyncio
async def test_conditions_gate_the_rule(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # only notify for high-value leads
    await client.post("/api/v1/notification-automation/rules", json={
        "name": "VIP", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "creator"}], "channels": ["in_app"], "title": "VIP {{title}}", "category": "lead",
        "conditions": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value": 10000}]}}, headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "Cheap", "title": "Small", "value": 100}, headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "Rich", "title": "Whale", "value": 50000}, headers=d["h_admin"])
    notifs = await _count_notifs(db, d["org"].id, d["admin"].id, "lead")
    titles = " ".join(n.title for n in notifs)
    assert "Whale" in titles and "Small" not in titles


@pytest.mark.asyncio
async def test_role_recipient_resolution(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # notify all Employees on lead.created
    await client.post("/api/v1/notification-automation/rules", json={
        "name": "Team ping", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "role", "value": "Employee"}], "channels": ["in_app"],
        "title": "Lead in", "category": "lead"}, headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "R", "title": "T"}, headers=d["h_admin"])
    emp_notifs = await _count_notifs(db, d["org"].id, d["emp"].id, "lead")
    assert len(emp_notifs) >= 1


@pytest.mark.asyncio
async def test_digest_batches_then_flush(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/notification-automation/rules", json={
        "name": "Digest me", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "creator"}], "channels": ["in_app"], "title": "Lead {{title}}",
        "category": "lead", "digest": True}, headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "A", "title": "One"}, headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "B", "title": "Two"}, headers=d["h_admin"])
    # digest items queued, no immediate lead notifications from the rule yet
    items = (await db.execute(select(NotificationDigestItem).filter(
        NotificationDigestItem.organization_id == d["org"].id, NotificationDigestItem.is_sent == False))).scalars().all()
    assert len(items) == 2
    # flush → one summary notification, items marked sent
    out = (await client.post("/api/v1/notification-automation/digests/flush", headers=d["h_admin"])).json()
    assert out["digests_sent"] == 1
    digest_notifs = await _count_notifs(db, d["org"].id, d["admin"].id, "digest")
    assert len(digest_notifs) == 1 and "2 update" in digest_notifs[0].title


@pytest.mark.asyncio
async def test_channel_failure_enqueues_retry(client: AsyncClient, setup: dict, db: AsyncSession, monkeypatch):
    d = setup
    # enable email preference for the admin on category "lead"
    db.add(NotificationPreference(organization_id=d["org"].id, user_id=d["admin"].id, category="lead", email=True))
    await db.commit()
    # force email sends to fail
    from app.services.notification_service import NotificationService
    async def fail_email(self, user, title, body): return False
    monkeypatch.setattr(NotificationService, "_send_email", fail_email)

    await client.post("/api/v1/notification-automation/rules", json={
        "name": "Email owner", "trigger_event": "lead.created", "entity_type": "lead",
        "recipients": [{"type": "creator"}], "channels": ["in_app", "email"], "title": "Deal", "category": "lead"},
        headers=d["h_admin"])
    await client.post("/api/v1/leads/", json={"last_name": "E", "title": "D"}, headers=d["h_admin"])
    # the email delivery is 'retrying' with a queue job; a send_email queue job exists
    retry = (await db.execute(select(NotificationDelivery).filter(
        NotificationDelivery.organization_id == d["org"].id, NotificationDelivery.channel == "email"))).scalars().first()
    assert retry is not None and retry.status == "retrying" and retry.queue_job_id is not None
    jobs = (await db.execute(select(QueueJob).filter(
        QueueJob.organization_id == d["org"].id, QueueJob.job_type == "send_email"))).scalars().all()
    assert len(jobs) >= 1
    # manual retry endpoint (still failing → failed)
    res = (await client.post(f"/api/v1/notification-automation/deliveries/{retry.id}/retry", headers=d["h_admin"])).json()
    assert res["status"] == "failed" and res["attempts"] == 2


@pytest.mark.asyncio
async def test_templates_crud_and_reports(client: AsyncClient, setup: dict):
    d = setup
    t = (await client.post("/api/v1/notification-automation/templates", json={
        "template_key": "welcome", "template_name": "Welcome", "channel": "email",
        "subject": "Hi {{name}}", "body": "Welcome {{name}}!"}, headers=d["h_admin"])).json()
    assert t["template_key"] == "welcome" and t["subject"] == "Hi {{name}}"
    # duplicate key rejected
    assert (await client.post("/api/v1/notification-automation/templates", json={
        "template_key": "welcome", "template_name": "Dup"}, headers=d["h_admin"])).status_code == 409
    lst = (await client.get("/api/v1/notification-automation/templates", headers=d["h_admin"])).json()
    assert any(x["template_key"] == "welcome" for x in lst)
    # dashboard + report
    dash = (await client.get("/api/v1/notification-automation/dashboard", headers=d["h_admin"])).json()
    assert "delivery_rate" in dash and "recent" in dash
    rep = (await client.get("/api/v1/notification-automation/report", headers=d["h_admin"])).json()
    assert "by_channel" in rep and "by_status" in rep

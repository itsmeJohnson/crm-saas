import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.notification import Notification, PushSubscription
from app.services.notification_service import NotificationService
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
        return ["SMS_MESSAGING", "EMAIL_MESSAGING", "WHATSAPP_MESSAGING"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "Notif Org", "slug": "notif-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@nc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True, "phone": "+15550001"})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@nc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True,
        "reporting_to_id": admin.id, "phone": "+15550002"})
    await db.commit()
    return {
        "org": org, "admin": admin, "emp": emp,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


async def _seed(db, org_id, user_id, category="lead", priority="normal", title="T"):
    n = Notification(organization_id=org_id, user_id=user_id, category=category, title=title,
                     body="b", priority=priority)
    db.add(n)
    await db.commit()
    return n


@pytest.mark.asyncio
async def test_priority_actions_and_history_filters(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    svc = NotificationService(db)
    await svc.create_notification(data["org"].id, data["emp"].id, "lead", "Hot lead", "b",
                                  priority="urgent", actions=[{"label": "Open", "url": "/leads"}])
    await svc.create_notification(data["org"].id, data["emp"].id, "task", "Task due", "b", priority="normal")
    await db.commit()

    # unfiltered
    r = await client.get("/api/v1/notifications/", headers=data["h_emp"])
    assert len(r.json()) == 2
    top = next(n for n in r.json() if n["title"] == "Hot lead")
    assert top["priority"] == "urgent"
    assert top["actions"][0]["label"] == "Open"
    assert top["channels_sent"] == ["in_app"]

    # category filter
    r = await client.get("/api/v1/notifications/", params={"category": "task"}, headers=data["h_emp"])
    assert len(r.json()) == 1 and r.json()[0]["category"] == "task"
    # priority filter
    r = await client.get("/api/v1/notifications/", params={"priority": "urgent"}, headers=data["h_emp"])
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_dismiss_and_unread_count(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    n1 = await _seed(db, data["org"].id, data["emp"].id)
    await _seed(db, data["org"].id, data["emp"].id)

    r = await client.get("/api/v1/notifications/unread-count", headers=data["h_emp"])
    assert r.json()["unread_count"] == 2

    # dismiss hides from the default list + drops unread
    r = await client.post(f"/api/v1/notifications/{n1.id}/dismiss", headers=data["h_emp"])
    assert r.json()["is_dismissed"] is True and r.json()["is_read"] is True
    r = await client.get("/api/v1/notifications/", headers=data["h_emp"])
    assert len(r.json()) == 1
    r = await client.get("/api/v1/notifications/", params={"include_dismissed": True}, headers=data["h_emp"])
    assert len(r.json()) == 2
    r = await client.get("/api/v1/notifications/unread-count", headers=data["h_emp"])
    assert r.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_bulk_read_by_ids_and_category(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    a = await _seed(db, data["org"].id, data["emp"].id, category="lead")
    b = await _seed(db, data["org"].id, data["emp"].id, category="lead")
    c = await _seed(db, data["org"].id, data["emp"].id, category="task")

    # by ids
    r = await client.post("/api/v1/notifications/bulk-read", json={"ids": [str(a.id)]}, headers=data["h_emp"])
    assert r.json()["marked_read"] == 1
    # by category
    r = await client.post("/api/v1/notifications/bulk-read", json={"category": "lead"}, headers=data["h_emp"])
    assert r.json()["marked_read"] == 1  # only b remained unread in 'lead'
    r = await client.get("/api/v1/notifications/unread-count", headers=data["h_emp"])
    assert r.json()["unread_count"] == 1  # the task one


@pytest.mark.asyncio
async def test_preferences_get_update(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/notifications/preferences", headers=data["h_emp"])
    assert r.status_code == 200
    cats = {p["category"] for p in r.json()}
    assert "lead" in cats and "billing" in cats
    assert all(p["in_app"] and not p["email"] for p in r.json())  # defaults

    r = await client.put("/api/v1/notifications/preferences", json={
        "items": [{"category": "lead", "in_app": True, "email": True, "sms": True}]}, headers=data["h_emp"])
    assert r.status_code == 200
    lead_pref = next(p for p in r.json() if p["category"] == "lead")
    assert lead_pref["email"] is True and lead_pref["sms"] is True


@pytest.mark.asyncio
async def test_dispatch_fans_out_per_prefs(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # opt the employee into email + SMS for the lead category
    await client.put("/api/v1/notifications/preferences", json={
        "items": [{"category": "lead", "in_app": True, "email": True, "sms": True}]}, headers=data["h_emp"])

    svc = NotificationService(db)
    n = await svc.dispatch(data["org"].id, data["emp"].id, "lead", "Fan out", "body", fanout=True)
    await db.commit()
    assert n is not None
    # email (mock) + sms (mock, emp has phone) + in_app all fired
    assert set(n.channels_sent) >= {"in_app", "email", "sms"}

    # a category the user did NOT opt into fans out to in-app only
    n2 = await svc.dispatch(data["org"].id, data["emp"].id, "billing", "Quiet", "body", fanout=True)
    await db.commit()
    assert n2.channels_sent == ["in_app"]


@pytest.mark.asyncio
async def test_in_app_muted_still_recorded(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # mute in-app for 'system'
    await client.put("/api/v1/notifications/preferences", json={
        "items": [{"category": "system", "in_app": False}]}, headers=data["h_emp"])
    svc = NotificationService(db)
    n = await svc.dispatch(data["org"].id, data["emp"].id, "system", "Muted", "b", fanout=False)
    await db.commit()
    # kept in history but no in_app channel
    assert n is not None
    assert "in_app" not in (n.channels_sent or [])


@pytest.mark.asyncio
async def test_push_subscribe_unsubscribe(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    r = await client.post("/api/v1/notifications/push/subscribe", json={
        "endpoint": "https://push.example/abc", "p256dh": "k", "auth": "a", "user_agent": "test"}, headers=data["h_emp"])
    assert r.status_code == 200
    subs = list((await db.execute(select(PushSubscription).filter(PushSubscription.user_id == data["emp"].id))).scalars().all())
    assert len(subs) == 1 and subs[0].is_deleted is False

    # idempotent re-subscribe
    await client.post("/api/v1/notifications/push/subscribe", json={"endpoint": "https://push.example/abc"}, headers=data["h_emp"])
    subs = list((await db.execute(select(PushSubscription).filter(
        PushSubscription.user_id == data["emp"].id, PushSubscription.is_deleted == False))).scalars().all())
    assert len(subs) == 1

    r = await client.post("/api/v1/notifications/push/unsubscribe", json={"endpoint": "https://push.example/abc"}, headers=data["h_emp"])
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_push_channel_delivers_when_opted_in(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await client.post("/api/v1/notifications/push/subscribe", json={"endpoint": "https://push.example/x"}, headers=data["h_emp"])
    await client.put("/api/v1/notifications/preferences", json={
        "items": [{"category": "lead", "in_app": True, "push": True}]}, headers=data["h_emp"])
    svc = NotificationService(db)
    n = await svc.dispatch(data["org"].id, data["emp"].id, "lead", "Pushed", "b", fanout=True)
    await db.commit()
    assert "push" in n.channels_sent


@pytest.mark.asyncio
async def test_broadcast_role_scoped_and_permissions(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    # employee cannot broadcast
    assert (await client.post("/api/v1/notifications/broadcast", json={"title": "x", "body": "y"}, headers=data["h_emp"])).status_code == 403

    # admin broadcasts to Employees only → reaches emp, not admin
    r = await client.post("/api/v1/notifications/broadcast", json={
        "title": "Team update", "body": "Please read", "category": "system", "priority": "high", "role": "Employee"},
        headers=data["h_admin"])
    assert r.status_code == 200
    assert r.json()["recipients"] == 1 and r.json()["sent"] == 1

    emp_notifs = (await db.execute(select(Notification).filter(Notification.user_id == data["emp"].id))).scalars().all()
    assert any(x.title == "Team update" and x.priority == "high" for x in emp_notifs)
    admin_notifs = (await db.execute(select(Notification).filter(Notification.user_id == data["admin"].id))).scalars().all()
    assert not any(x.title == "Team update" for x in admin_notifs)


@pytest.mark.asyncio
async def test_stats_and_unread_by_category(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    await _seed(db, data["org"].id, data["emp"].id, category="lead", priority="urgent")
    await _seed(db, data["org"].id, data["emp"].id, category="lead")
    n = await _seed(db, data["org"].id, data["emp"].id, category="task")
    await client.patch(f"/api/v1/notifications/{n.id}/read", headers=data["h_emp"])

    r = await client.get("/api/v1/notifications/stats", headers=data["h_emp"])
    st = r.json()
    assert st["total"] == 3 and st["read"] == 1 and st["unread"] == 2
    assert st["read_rate"] == 33.3
    cats = {b["label"]: b["count"] for b in st["by_category"]}
    assert cats == {"lead": 2, "task": 1}

    r = await client.get("/api/v1/notifications/unread-by-category", headers=data["h_emp"])
    ubc = {x["category"]: x["count"] for x in r.json()}
    assert ubc.get("lead") == 2 and "task" not in ubc  # task was read


@pytest.mark.asyncio
async def test_categories_endpoint(client: AsyncClient, setup: dict):
    data = setup
    r = await client.get("/api/v1/notifications/categories", headers=data["h_emp"])
    assert r.status_code == 200
    assert "lead" in r.json() and "campaign" in r.json()

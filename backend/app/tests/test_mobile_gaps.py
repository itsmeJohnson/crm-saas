"""Mobile platform backend gaps (Sprint 9):
  Gap A — native push device-token registration + dispatch fan-out (FCM/APNS).
  Gap B — incremental delta-sync via ?updated_after= on the leads list.
Both reuse existing services; no business logic is duplicated.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.notification import DeviceToken
from app.services.notification_service import NotificationService


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Mobile Org", "slug": "mobile-org"})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": "admin@mobile.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    stage = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalar()
    if not stage:
        s = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(s); await db.commit(); stage = s.id
    return {
        "org": org, "admin": admin, "stage": stage,
        "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
    }


# ---- Gap A ----

@pytest.mark.asyncio
async def test_register_device_is_idempotent_then_unregister(client: AsyncClient, setup, db: AsyncSession):
    h = setup["headers"]
    body = {"token": "fcm-token-abc", "platform": "fcm", "device_name": "Pixel 8"}

    r1 = await client.post("/api/v1/notifications/devices", json=body, headers=h)
    assert r1.status_code == 200, r1.text
    assert r1.json()["platform"] == "fcm"

    # Re-registering the same token must not create a duplicate.
    r2 = await client.post("/api/v1/notifications/devices", json=body, headers=h)
    assert r2.status_code == 200
    rows = (await db.execute(select(DeviceToken).filter(DeviceToken.token == "fcm-token-abc"))).scalars().all()
    assert len(rows) == 1 and rows[0].is_active_token is True

    r3 = await client.post("/api/v1/notifications/devices/unregister",
                           json={"token": "fcm-token-abc"}, headers=h)
    assert r3.status_code == 204
    await db.refresh(rows[0])
    assert rows[0].is_deleted is True and rows[0].is_active_token is False


@pytest.mark.asyncio
async def test_register_device_rejects_bad_platform(client: AsyncClient, setup):
    r = await client.post("/api/v1/notifications/devices",
                          json={"token": "t", "platform": "windows"}, headers=setup["headers"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_push_dispatch_fans_out_to_device_tokens(setup, db: AsyncSession):
    admin, org = setup["admin"], setup["org"]
    svc = NotificationService(db)
    # No device yet → nothing to push.
    assert await svc._send_push(org.id, admin.id, "t", "b", None) is False
    # Register an APNS device, then the (mock) native sender reports success.
    await svc.register_device(admin, {"token": "apns-xyz", "platform": "apns"})
    assert await svc._send_push(org.id, admin.id, "Reminder", "Call now", "/leads") is True


# ---- Gap B ----

@pytest.mark.asyncio
async def test_leads_updated_after_returns_only_changed(client: AsyncClient, setup, db: AsyncSession):
    org, admin, stage = setup["org"], setup["admin"], setup["stage"]
    now = datetime.now(timezone.utc)

    old = Lead(organization_id=org.id, last_name="Old", title="Old deal", status="New",
               stage_id=stage, created_by=admin.id, assigned_user_id=admin.id)
    new = Lead(organization_id=org.id, last_name="New", title="New deal", status="New",
               stage_id=stage, created_by=admin.id, assigned_user_id=admin.id)
    db.add_all([old, new]); await db.flush()
    # Set updated_at via a Core UPDATE — an explicit value in the SET clause
    # bypasses the column's onupdate=now(), which an ORM re-flush would trigger.
    await db.execute(update(Lead).where(Lead.id == old.id).values(updated_at=now - timedelta(days=10)))
    await db.execute(update(Lead).where(Lead.id == new.id).values(updated_at=now - timedelta(days=1)))
    await db.commit()

    cutoff = (now - timedelta(days=5)).isoformat()
    r = await client.get("/api/v1/leads/", params={"updated_after": cutoff}, headers=setup["headers"])
    assert r.status_code == 200, r.text
    titles = {lead["title"] for lead in r.json()}
    assert "New deal" in titles and "Old deal" not in titles

    # Without the cursor, both come back.
    r_all = await client.get("/api/v1/leads/", headers=setup["headers"])
    all_titles = {lead["title"] for lead in r_all.json()}
    assert {"Old deal", "New deal"} <= all_titles

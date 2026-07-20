import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from app.models.pipeline import PipelineStage


@pytest.fixture
async def setup_notification_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Notify Org", "slug": "notify-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@notify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin",
        "last_name": "One",
        "role": "OrgAdmin",
        "is_active": True,
    })
    manager = await user_repo.create_user(org.id, {
        "email": "manager@notify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": admin.id,
    })
    tl = await user_repo.create_user(org.id, {
        "email": "tl@notify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id,
    })
    tc1 = await user_repo.create_user(org.id, {
        "email": "tc1@notify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC1",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id,
    })
    tc2 = await user_repo.create_user(org.id, {
        "email": "tc2@notify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC2",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id,
    })
    await db.commit()

    # A second, unrelated org — used to prove tenant isolation.
    other_org = await org_repo.create({"name": "Other Org", "slug": "other-notify-org"})
    other_admin = await user_repo.create_user(other_org.id, {
        "email": "admin@othernotify.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Other",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True,
    })
    await db.commit()

    return {
        "org": org,
        "admin": admin,
        "manager": manager,
        "tl": tl,
        "tc1": tc1,
        "tc2": tc2,
        "other_org": other_org,
        "other_admin": other_admin,
        "headers_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "headers_tl": {"Authorization": f"Bearer {create_access_token(tl.id)}"},
        "headers_tc1": {"Authorization": f"Bearer {create_access_token(tc1.id)}"},
        "headers_tc2": {"Authorization": f"Bearer {create_access_token(tc2.id)}"},
        "headers_other_admin": {"Authorization": f"Bearer {create_access_token(other_admin.id)}"},
    }


@pytest.mark.asyncio
async def test_notification_service_crud(db: AsyncSession, setup_notification_data: dict):
    data = setup_notification_data
    service = NotificationService(db)

    notif = await service.create_notification(
        organization_id=data["org"].id,
        user_id=data["tc1"].id,
        category="lead",
        title="Test notification",
        body="Body text",
        link_url="/leads",
    )
    await db.commit()
    assert notif.is_read is False

    count = await service.get_unread_count(data["org"].id, data["tc1"].id)
    assert count == 1

    records, total = await service.paginate_for_user(data["org"].id, data["tc1"].id)
    assert total == 1
    assert records[0].id == notif.id

    updated = await service.mark_read(data["org"].id, data["tc1"].id, notif.id)
    assert updated.is_read is True
    assert updated.read_at is not None

    count_after = await service.get_unread_count(data["org"].id, data["tc1"].id)
    assert count_after == 0


@pytest.mark.asyncio
async def test_notification_mark_all_read(db: AsyncSession, setup_notification_data: dict):
    data = setup_notification_data
    service = NotificationService(db)

    for i in range(3):
        await service.create_notification(
            organization_id=data["org"].id,
            user_id=data["tc1"].id,
            category="system",
            title=f"Notification {i}",
            body="Body",
        )
    await db.commit()

    assert await service.get_unread_count(data["org"].id, data["tc1"].id) == 3
    marked = await service.mark_all_read(data["org"].id, data["tc1"].id)
    assert marked == 3
    assert await service.get_unread_count(data["org"].id, data["tc1"].id) == 0


@pytest.mark.asyncio
async def test_notification_tenant_isolation(client: AsyncClient, db: AsyncSession, setup_notification_data: dict):
    """A notification belonging to one org must be invisible and unmodifiable from another org's session."""
    data = setup_notification_data
    service = NotificationService(db)

    notif = await service.create_notification(
        organization_id=data["org"].id,
        user_id=data["admin"].id,
        category="system",
        title="Org A notification",
        body="Should never be visible to Org B",
    )
    await db.commit()

    # Org B's admin sees an empty list, not Org A's notification.
    res_list = await client.get("/api/v1/notifications/", headers=data["headers_other_admin"])
    assert res_list.status_code == 200
    assert res_list.json() == []

    # Org B's admin cannot mark Org A's notification as read.
    res_mark = await client.patch(f"/api/v1/notifications/{notif.id}/read", headers=data["headers_other_admin"])
    assert res_mark.status_code == 404

    # Org A's own admin still can't see another user's notification (it belongs to admin, not tl).
    res_tl_list = await client.get("/api/v1/notifications/", headers=data["headers_tl"])
    assert res_tl_list.status_code == 200
    assert res_tl_list.json() == []


@pytest.mark.asyncio
async def test_lead_creation_with_assignment_sends_notification(client: AsyncClient, db: AsyncSession, setup_notification_data: dict):
    data = setup_notification_data

    payload = {
        "first_name": "Lead",
        "last_name": "Assigned",
        "title": "New Opportunity",
        "assigned_user_id": str(data["tc1"].id),
    }
    res = await client.post("/api/v1/leads/", json=payload, headers=data["headers_admin"])
    assert res.status_code == 201

    # tc1 (the assignee) should have exactly one unread notification.
    res_notifs = await client.get("/api/v1/notifications/", headers=data["headers_tc1"])
    assert res_notifs.status_code == 200
    notifs = res_notifs.json()
    assert len(notifs) == 1
    assert notifs[0]["category"] == "lead"
    assert notifs[0]["is_read"] is False

    # The actor (admin) who created and assigned it should NOT be notified of their own action.
    res_admin_notifs = await client.get("/api/v1/notifications/", headers=data["headers_admin"])
    assert res_admin_notifs.json() == []


@pytest.mark.asyncio
async def test_lead_transfer_sends_batched_notification(client: AsyncClient, db: AsyncSession, setup_notification_data: dict):
    data = setup_notification_data
    from app.models.lead import Lead

    res_stage = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == data["org"].id,
            PipelineStage.is_system_default == True,
        )
    )
    default_stage_id = res_stage.scalar()

    for i in range(3):
        db.add(Lead(
            organization_id=data["org"].id,
            first_name=f"Lead_{i}",
            last_name="Transfer",
            title=f"Opportunity {i}",
            assigned_user_id=data["tl"].id,
            created_by=data["admin"].id,
            stage_id=default_stage_id,
        ))
    await db.commit()

    payload = {
        "source_user_id": str(data["tl"].id),
        "destination_user_ids": [str(data["tc1"].id)],
        "quantity": 3,
    }
    res = await client.post("/api/v1/leads/transfer", json=payload, headers=data["headers_tl"])
    assert res.status_code == 200
    assert res.json()["transferred_count"] == 3

    # tc1 gets exactly ONE batched notification for all 3 leads, not 3 separate ones.
    res_notifs = await client.get("/api/v1/notifications/", headers=data["headers_tc1"])
    notifs = res_notifs.json()
    assert len(notifs) == 1
    assert "3 lead" in notifs[0]["body"]

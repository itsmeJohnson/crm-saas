import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository

@pytest.mark.asyncio
async def test_audit_repository(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    # 1. Setup two organizations
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Setup user to act as actor
    user_data = {
        "email": "actor@test.com",
        "hashed_password": "hash",
        "first_name": "Bob",
        "last_name": "Actor",
        "role": "Manager",
        "is_active": True
    }
    user = await user_repo.create_user(org_a.id, user_data)
    await db.commit()

    # 3. Create logs
    log_a = await audit_repo.create_log(org_a.id, {
        "actor_user_id": user.id,
        "action": "USER_INVITED",
        "resource_type": "invitation",
        "resource_id": "some_id",
        "action_metadata": {"key": "valA"}
    })

    log_b = await audit_repo.create_log(org_b.id, {
        "actor_user_id": None,
        "action": "TENANT_REGISTERED",
        "resource_type": "tenant",
        "resource_id": str(org_b.id),
        "action_metadata": {"key": "valB"}
    })
    await db.commit()

    # 4. Check list_logs and isolation
    logs_a = await audit_repo.list_logs(org_a.id)
    assert len(logs_a) == 1
    assert logs_a[0].action == "USER_INVITED"
    assert logs_a[0].action_metadata == {"key": "valA"}

    logs_b = await audit_repo.list_logs(org_b.id)
    assert len(logs_b) == 1
    assert logs_b[0].action == "TENANT_REGISTERED"

    # 5. Check list_user_logs and isolation
    user_logs_a = await audit_repo.list_user_logs(org_a.id, user.id)
    assert len(user_logs_a) == 1
    assert user_logs_a[0].id == log_a.id

    user_logs_b = await audit_repo.list_user_logs(org_b.id, user.id)
    assert len(user_logs_b) == 0

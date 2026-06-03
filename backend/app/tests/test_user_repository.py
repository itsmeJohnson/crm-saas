import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository

@pytest.mark.asyncio
async def test_user_repository_crud_and_tenant_isolation(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Setup two organizations (Tenant A and Tenant B)
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Create users under each organization
    user_a_data = {
        "email": "userA@test.com",
        "hashed_password": "hash",
        "first_name": "Alice",
        "last_name": "Smith",
        "role": "OrgAdmin",
        "is_active": True
    }
    user_a = await user_repo.create_user(org_a.id, user_a_data)

    user_b_data = {
        "email": "userB@test.com",
        "hashed_password": "hash",
        "first_name": "Bob",
        "last_name": "Jones",
        "role": "Employee",
        "is_active": True
    }
    user_b = await user_repo.create_user(org_b.id, user_b_data)
    await db.commit()

    # 3. Test tenant isolation on get_user_by_id
    assert await user_repo.get_user_by_id(org_a.id, user_a.id) is not None
    assert await user_repo.get_user_by_id(org_b.id, user_a.id) is None

    # 4. Test tenant isolation on get_user_by_email
    assert await user_repo.get_user_by_email(org_a.id, "userA@test.com") is not None
    assert await user_repo.get_user_by_email(org_b.id, "userA@test.com") is None

    # 5. Test pagination and listing scoping
    users_a, total_a = await user_repo.paginate_users(org_a.id, skip=0, limit=10)
    assert len(users_a) == 1
    assert total_a == 1
    assert users_a[0].id == user_a.id

    users_b, total_b = await user_repo.paginate_users(org_b.id, skip=0, limit=10)
    assert len(users_b) == 1
    assert total_b == 1
    assert users_b[0].id == user_b.id

    # 6. Test soft delete exclusion
    deleted_user = await user_repo.soft_delete_user(org_a.id, user_a.id)
    assert deleted_user is not None
    assert deleted_user.is_deleted is True
    await db.commit()

    assert await user_repo.get_user_by_id(org_a.id, user_a.id) is None
    users_a_after, total_a_after = await user_repo.paginate_users(org_a.id, skip=0, limit=10)
    assert len(users_a_after) == 0
    assert total_a_after == 0

    # 7. Test counting org admins
    user_b2_data = {
        "email": "adminB@test.com",
        "hashed_password": "hash",
        "first_name": "Boss",
        "last_name": "Jones",
        "role": "OrgAdmin",
        "is_active": True
    }
    await user_repo.create_user(org_b.id, user_b2_data)
    await db.commit()
    
    assert await user_repo.count_org_admins(org_b.id) == 1
    assert await user_repo.count_org_admins(org_a.id) == 0

import pytest
import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

@pytest.mark.asyncio
async def test_user_service_operations(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    user_service = UserService(db)

    # 1. Setup organization and users
    org = await org_repo.create({"name": "CRM Org", "slug": "crm-org"})
    await db.commit()

    # Create OrgAdmin actor
    admin = await user_repo.create_user(org.id, {
        "email": "admin@crm.com",
        "hashed_password": "hash",
        "first_name": "Admin",
        "last_name": "User",
        "role": "OrgAdmin",
        "is_active": True
    })

    # Create Manager actor
    manager = await user_repo.create_user(org.id, {
        "email": "manager@crm.com",
        "hashed_password": "hash",
        "first_name": "Manager",
        "last_name": "User",
        "role": "Manager",
        "is_active": True
    })
    await db.commit()

    # 2. Test create user: Admin creates Manager
    new_manager_data = {
        "email": "new_manager@crm.com",
        "first_name": "New",
        "last_name": "Manager",
        "role": "Manager",
        "password": "securepassword123"
    }
    new_manager = await user_service.create_user(admin, new_manager_data)
    assert new_manager.email == "new_manager@crm.com"
    assert new_manager.role == "Manager"

    # 3. Test hierarchy: Manager cannot create another Manager
    another_manager_data = {
        "email": "another@crm.com",
        "first_name": "Another",
        "last_name": "Manager",
        "role": "Manager",
        "password": "securepassword123"
    }
    with pytest.raises(HTTPException) as exc_info:
        await user_service.create_user(manager, another_manager_data)
    assert exc_info.value.status_code == 403

    # 4. Test self profile update exceptions: manager updates self
    self_update = await user_service.update_user(manager, manager.id, {
        "first_name": "UpdatedManager",
        "password": "newpassword123"
    })
    assert self_update.first_name == "UpdatedManager"

    # 5. Test self profile update: cannot demote self role
    with pytest.raises(HTTPException) as exc_info:
        await user_service.update_user(manager, manager.id, {"role": "Employee"})
    assert exc_info.value.status_code == 403

    # 6. Test last OrgAdmin protection (demoting last admin should fail)
    with pytest.raises(HTTPException) as exc_info:
        await user_service.update_user(admin, admin.id, {"role": "Employee"})
    assert exc_info.value.status_code == 400
    assert "final OrgAdmin" in exc_info.value.detail

    # 7. Test last OrgAdmin protection (deactivating last admin should fail)
    with pytest.raises(HTTPException) as exc_info:
        await user_service.toggle_active(admin, admin.id, False)
    assert exc_info.value.status_code == 400  # Cannot self deactivate anyway

    # Create another user to toggle (demote/deactivate admin)
    admin_2 = await user_repo.create_user(org.id, {
        "email": "admin2@crm.com",
        "hashed_password": "hash",
        "first_name": "Admin2",
        "last_name": "User",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # Now we have 2 admins. Deactivating one should succeed.
    deactivated = await user_service.toggle_active(admin, admin_2.id, False)
    assert deactivated.is_active is False

    # Try deactivating the remaining admin (should fail with deactivated actor block)
    with pytest.raises(HTTPException) as exc_info:
        await user_service.toggle_active(admin_2, admin.id, False)
    assert exc_info.value.status_code == 403
    assert "deactivated" in exc_info.value.detail

    # 8. Test soft delete and last admin protection
    # Delete deactivated admin_2 (should succeed)
    deleted_admin = await user_service.soft_delete_user(admin, admin_2.id)
    assert deleted_admin.is_deleted is True

    # Delete remaining admin (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await user_service.soft_delete_user(admin, admin.id)  # Cannot self delete anyway
    assert exc_info.value.status_code == 400

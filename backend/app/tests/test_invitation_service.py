import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.invitation_repository import InvitationRepository
from app.services.invitation_service import InvitationService
from app.models.invitation import UserInvitation

@pytest.mark.asyncio
async def test_invitation_service_flow(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    invite_repo = InvitationRepository(db)
    invite_service = InvitationService(db)

    # 1. Setup organization and actors
    org = await org_repo.create({"name": "CRM Org", "slug": "crm-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@crm.com",
        "hashed_password": "hash",
        "first_name": "Admin",
        "last_name": "User",
        "role": "OrgAdmin",
        "is_active": True
    })

    manager = await user_repo.create_user(org.id, {
        "email": "manager@crm.com",
        "hashed_password": "hash",
        "first_name": "Manager",
        "last_name": "User",
        "role": "Manager",
        "is_active": True
    })
    await db.commit()

    # 2. Test invite user
    invite = await invite_service.invite_user(admin, "employee@test.com", "Employee")
    assert invite.email == "employee@test.com"
    assert invite.role == "Employee"
    assert invite.accepted is False

    # 3. Test duplicate pending invite prevention
    with pytest.raises(HTTPException) as exc_info:
        await invite_service.invite_user(admin, "employee@test.com", "Employee")
    assert exc_info.value.status_code == 400
    assert "pending invitation already exists" in exc_info.value.detail

    # 4. Test hierarchy validation: Manager cannot invite OrgAdmin
    with pytest.raises(HTTPException) as exc_info:
        await invite_service.invite_user(manager, "boss@test.com", "OrgAdmin")
    assert exc_info.value.status_code == 403

    # 5. Test accept invitation
    user = await invite_service.accept_invite(
        token=invite.token,
        password="newsecurepassword123",
        first_name="Invited",
        last_name="Employee"
    )
    assert user.email == "employee@test.com"
    assert user.role == "Employee"
    assert user.is_invited is True
    assert user.is_active is True

    # 6. Test invite reuse prevention (invite is accepted, should fail)
    with pytest.raises(HTTPException) as exc_info:
        await invite_service.accept_invite(
            token=invite.token,
            password="newsecurepassword123",
            first_name="Invited",
            last_name="Employee"
        )
    assert exc_info.value.status_code == 400
    assert "no longer active" in exc_info.value.detail

    # 7. Test expired token validation
    expired_invite_data = {
        "organization_id": org.id,
        "email": "expired@test.com",
        "role": "Employee",
        "token": "expired_token",
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "created_by": admin.id
    }
    await invite_repo.create(expired_invite_data)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await invite_service.accept_invite(
            token="expired_token",
            password="newsecurepassword123",
            first_name="Expired",
            last_name="User"
        )
    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail

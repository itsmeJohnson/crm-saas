import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.invitation_repository import InvitationRepository

@pytest.mark.asyncio
async def test_invitation_repository(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    invite_repo = InvitationRepository(db)

    # 1. Setup two organizations
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Setup user to act as creator
    user_data = {
        "email": "creator@test.com",
        "hashed_password": "hash",
        "first_name": "John",
        "last_name": "Creator",
        "role": "OrgAdmin",
        "is_active": True
    }
    user = await user_repo.create_user(org_a.id, user_data)
    await db.commit()

    # 3. Create invitations
    invite_a_data = {
        "email": "inviteeA@test.com",
        "role": "Employee",
        "token": "tokenA",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "created_by": user.id
    }
    invite_a = await invite_repo.create_invitation(org_a.id, invite_a_data)

    invite_b_data = {
        "email": "inviteeB@test.com",
        "role": "Employee",
        "token": "tokenB",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "created_by": user.id
    }
    invite_b = await invite_repo.create_invitation(org_b.id, invite_b_data)
    await db.commit()

    # 4. Test tenant isolation on get_by_token
    assert await invite_repo.get_by_token(org_a.id, "tokenA") is not None
    assert await invite_repo.get_by_token(org_b.id, "tokenA") is None

    # 5. Check pending list and isolation
    pending_a = await invite_repo.get_pending_invites(org_a.id)
    assert len(pending_a) == 1
    assert pending_a[0].token == "tokenA"

    pending_b = await invite_repo.get_pending_invites(org_b.id)
    assert len(pending_b) == 1
    assert pending_b[0].token == "tokenB"

    # 6. Test check existing pending invite
    assert await invite_repo.existing_pending_invite(org_a.id, "inviteeA@test.com") is not None
    assert await invite_repo.existing_pending_invite(org_b.id, "inviteeA@test.com") is None

    # 7. Test mark accepted
    accepted_invite = await invite_repo.mark_accepted(org_a.id, invite_a.id)
    assert accepted_invite.accepted is True
    await db.commit()
    
    assert len(await invite_repo.get_pending_invites(org_a.id)) == 0

    # 8. Test revoke invite
    revoked_invite = await invite_repo.revoke_invite(org_b.id, invite_b.id)
    assert revoked_invite.revoked is True
    await db.commit()

    assert len(await invite_repo.get_pending_invites(org_b.id)) == 0

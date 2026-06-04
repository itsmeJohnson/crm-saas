import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Sequence
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.user_repository import UserRepository
from app.services.permission_service import PermissionService
from app.services.audit_service import AuditService
from app.core.security import get_password_hash
from app.models.user import User
from app.models.invitation import UserInvitation

class InvitationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.invite_repo = InvitationRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def invite_user(self, actor: User, email: str, role: str) -> UserInvitation:
        """Invite a new user to join the tenant organization."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        # Enforce RBAC Role Hierarchy
        PermissionService.check_user_management_permission(actor, role)

        # Check if email is already registered globally
        existing_user = await self.user_repo.get_by_email_global(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User with this email is already registered"
            )

        # Check for active pending invitations for this email in this organization
        existing_invite = await self.invite_repo.existing_pending_invite(actor.organization_id, email)
        if existing_invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="A pending invitation already exists for this email"
            )

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        invite_data = {
            "email": email,
            "role": role,
            "token": token,
            "expires_at": expires_at,
            "created_by": actor.id
        }

        invite = await self.invite_repo.create_invitation(actor.organization_id, invite_data)

        # Audit log event
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="INVITE_CREATED",
            resource_type="invitation",
            resource_id=str(invite.id),
            action_metadata={"email": email, "role": role}
        )

        return invite

    async def get_pending_invites(self, actor: User) -> Sequence[UserInvitation]:
        """Fetch pending, non-expired, and non-revoked invitations in the tenant."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        if actor.role == "Employee":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough privileges"
            )
        return await self.invite_repo.get_pending_invites(actor.organization_id)

    async def revoke_invite(self, actor: User, invite_id: uuid.UUID) -> UserInvitation:
        """Revoke a pending user invitation."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )

        invite = await self.invite_repo.get(invite_id)
        if not invite or invite.organization_id != actor.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Invitation not found"
            )

        PermissionService.check_user_management_permission(actor, invite.role)

        if invite.accepted or invite.revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invitation is already accepted or revoked"
            )

        revoked = await self.invite_repo.revoke_invite(actor.organization_id, invite_id)

        # Audit log event
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="INVITE_REVOKED",
            resource_type="invitation",
            resource_id=str(invite_id),
            action_metadata={"email": invite.email}
        )

        return revoked

    async def accept_invite(self, token: str, password: str, first_name: str, last_name: str) -> User:
        """Public endpoint logic to register a user via invitation token."""
        query = select(UserInvitation).filter(UserInvitation.token == token)
        result = await self.db.execute(query)
        invite = result.scalars().first()

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Invalid invitation token"
            )

        if invite.accepted or invite.revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invitation is no longer active"
            )

        invite_expires = invite.expires_at
        if invite_expires.tzinfo is None:
            invite_expires = invite_expires.replace(tzinfo=timezone.utc)

        if invite_expires < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invitation has expired"
            )

        existing_user = await self.user_repo.get_by_email_global(invite.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User with this email is already registered"
            )

        # Create user profile
        hashed_password = get_password_hash(password)
        user_data = {
            "email": invite.email,
            "hashed_password": hashed_password,
            "first_name": first_name,
            "last_name": last_name,
            "role": invite.role,
            "is_active": True,
            "is_verified": True,
            "is_invited": True
        }
        user = await self.user_repo.create_user(invite.organization_id, user_data)

        # Mark accepted
        await self.invite_repo.mark_accepted(invite.organization_id, invite.id)

        # Audit log event
        await self.audit_service.log_event(
            organization_id=invite.organization_id,
            actor_user_id=user.id,
            action="INVITE_ACCEPTED",
            resource_type="invitation",
            resource_id=str(invite.id),
            action_metadata={"email": invite.email, "user_id": str(user.id)}
        )

        return user

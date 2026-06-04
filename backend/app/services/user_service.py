import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import UserRepository
from app.services.permission_service import PermissionService
from app.services.audit_service import AuditService
from app.core.security import get_password_hash
from app.models.user import User

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def get_user_by_id(self, actor: User, user_id: uuid.UUID) -> User:
        """Fetch a specific user inside the same organization."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        user = await self.user_repo.get_user_by_id(actor.organization_id, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        if actor.id != user_id:
            PermissionService.check_user_management_permission(actor, user.role)
        return user

    async def create_user(self, actor: User, user_data: dict) -> User:
        """Create a user after verifying actor RBAC permissions."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        # Enforce RBAC Role Hierarchy: Manager can only create Employee, Employee cannot create anyone
        PermissionService.check_user_management_permission(actor, user_data.get("role", "Employee"))

        # Check global email uniqueness
        existing = await self.user_repo.get_by_email_global(user_data["email"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )

        if "password" in user_data:
            user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
        
        user = await self.user_repo.create_user(actor.organization_id, user_data)
        
        # Write Audit Log
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_CREATED",
            resource_type="user",
            resource_id=str(user.id),
            action_metadata={"email": user.email, "role": user.role}
        )
        
        return user

    async def update_user(self, actor: User, user_id: uuid.UUID, update_data: dict) -> User:
        """Update user properties after verifying actor role permissions."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)

        # Enforce Hierarchy for role changes
        is_self = actor.id == user_id
        if is_self:
            if "role" in update_data and update_data["role"] != actor.role:
                if actor.role != "OrgAdmin":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You cannot change your own role"
                    )
            if "is_active" in update_data and not update_data["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot deactivate yourself"
                )
        else:
            # Manager cannot edit OrgAdmin or Manager, Employee cannot edit anyone
            PermissionService.check_user_management_permission(actor, target_user.role)
            if "role" in update_data:
                PermissionService.check_user_management_permission(actor, update_data["role"])

        # Prevent demoting the final OrgAdmin
        if target_user.role == "OrgAdmin" and "role" in update_data and update_data["role"] != "OrgAdmin":
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the final OrgAdmin user of this organization"
                )

        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        updated = await self.user_repo.update_user(actor.organization_id, user_id, update_data)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_UPDATED",
            resource_type="user",
            resource_id=str(user_id),
            action_metadata={"updated_fields": list(update_data.keys())}
        )

        return updated

    async def toggle_active(self, actor: User, user_id: uuid.UUID, is_active: bool) -> User:
        """Activate or deactivate user account status."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)
        
        if actor.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You cannot deactivate yourself"
            )

        PermissionService.check_user_management_permission(actor, target_user.role)

        # Prevent deactivating the last OrgAdmin
        if target_user.role == "OrgAdmin" and not is_active:
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the final OrgAdmin user of this organization"
                )

        updated = await self.user_repo.toggle_active(actor.organization_id, user_id, is_active)

        action_name = "USER_ACTIVATED" if is_active else "USER_DEACTIVATED"
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action=action_name,
            resource_type="user",
            resource_id=str(user_id)
        )

        return updated

    async def soft_delete_user(self, actor: User, user_id: uuid.UUID) -> User:
        """Soft delete a user from organization listing."""
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Actor account is deactivated"
            )
        
        target_user = await self.get_user_by_id(actor, user_id)
        
        if actor.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You cannot delete yourself"
            )

        PermissionService.check_user_management_permission(actor, target_user.role)

        # Prevent deleting the last OrgAdmin
        if target_user.role == "OrgAdmin":
            admin_count = await self.user_repo.count_org_admins(actor.organization_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the final OrgAdmin user of this organization"
                )

        deleted = await self.user_repo.soft_delete_user(actor.organization_id, user_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="USER_DELETED",
            resource_type="user",
            resource_id=str(user_id)
        )

        return deleted

    async def paginate_users(self, actor: User, skip: int = 0, limit: int = 100, search_query: str | None = None) -> Tuple[Sequence[User], int]:
        """Fetch paginated, searchable list of users belonging to the tenant."""
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
        return await self.user_repo.paginate_users(actor.organization_id, skip, limit, search_query)

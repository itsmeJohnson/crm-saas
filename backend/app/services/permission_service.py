import uuid
from fastapi import HTTPException, status
from app.models.user import User

class PermissionService:
    @staticmethod
    def verify_role_hierarchy(actor_role: str, target_role: str) -> bool:
        """
        Enforce hierarchical RBAC control.
        - OrgAdmin can manage any role.
        - Manager can only manage Employee.
        - Employee cannot manage anyone.
        """
        if actor_role == "OrgAdmin":
            return True
        if actor_role == "Manager":
            return target_role == "Employee"
        return False

    @staticmethod
    def check_user_management_permission(
        actor: User, 
        target_user_role: str, 
        target_reporting_to_id: uuid.UUID | None = None, 
        is_tl: bool = False
    ) -> None:
        """
        Verify if the actor is active and has permissions to manipulate a target user with a given role.
        Raises 403 Forbidden on failure.
        """
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        # If the actor is a Team Leader (is_tl=True), they can manage an Employee reporting to them.
        if actor.role == "Employee" and is_tl and target_user_role == "Employee" and target_reporting_to_id == actor.id:
            return
            
        if not PermissionService.verify_role_hierarchy(actor.role, target_user_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage this role level"
            )

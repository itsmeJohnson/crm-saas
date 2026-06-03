from typing import List, Annotated
from fastapi import Depends, HTTPException, status
from app.dependencies.auth import get_current_active_user
from app.models.user import User

async def require_active_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """Dependency verifying that the user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return current_user

class RoleRequired:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Annotated[User, Depends(require_active_user)]) -> User:
        """Call method to check current active user role."""
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough privileges"
            )
        return current_user

def require_role(allowed_roles: List[str]):
    return RoleRequired(allowed_roles)

def require_user_management_permission():
    """Dependency enforcing that the user has administrative/management rights."""
    return require_role(["OrgAdmin", "Manager"])

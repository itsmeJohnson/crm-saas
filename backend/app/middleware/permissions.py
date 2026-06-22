from typing import List, Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.core.database import get_db
from app.core.context import mask_phone_ctx

async def require_active_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """Dependency verifying that the user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    # Check if the user is a Telecaller (Employee reporting to a TL/Employee)
    mask_phone = False
    if current_user.role == "Employee" and current_user.reporting_to_id:
        parent_query = select(User.role).filter(User.id == current_user.reporting_to_id)
        res = await db.execute(parent_query)
        parent_role = res.scalar()
        if parent_role == "Employee":
            mask_phone = True
            
    mask_phone_ctx.set(mask_phone)
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

async def check_is_team_leader(user: User, db: AsyncSession) -> bool:
    """Check if the user is a Team Leader (Employee who reports to a Manager)."""
    if user.role != "Employee" or not user.reporting_to_id:
        return False
    parent_res = await db.execute(select(User.role).filter(User.id == user.reporting_to_id))
    parent_role = parent_res.scalar()
    return parent_role == "Manager"

async def require_tl_or_above(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """Dependency enforcing that the user is a Team Leader, Manager, or Admin."""
    if current_user.role in ["SuperAdmin", "OrgAdmin", "Manager"]:
        return current_user
    
    is_tl = await check_is_team_leader(current_user, db)
    if is_tl:
        return current_user
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have enough privileges"
    )

from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.user import UserCreate
from app.schemas.invitation import InvitationCreate
from app.services.subscription_service import SubscriptionService

async def check_user_creation_limit_dep(
    user_in: UserCreate,
    actor: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    """FastAPI dependency to check subscription limits before creating a user."""
    service = SubscriptionService(db)
    await service.check_user_creation_limit(
        organization_id=actor.organization_id,
        role=user_in.role,
        reporting_to_id=user_in.reporting_to_id
    )

async def check_user_invite_limit_dep(
    invite_in: InvitationCreate,
    actor: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    """FastAPI dependency to check subscription limits before sending an invitation."""
    service = SubscriptionService(db)
    await service.check_user_creation_limit(
        organization_id=actor.organization_id,
        role=invite_in.role,
        reporting_to_id=None
    )

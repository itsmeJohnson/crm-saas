from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.organization import OrganizationResponse, OrganizationUpdate
from app.services.org_service import OrganizationService
from app.dependencies.auth import get_current_active_user, RoleChecker
from app.models.user import User

router = APIRouter()

@router.get("/my", response_model=OrganizationResponse)
async def get_my_org(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    org_service = OrganizationService(db)
    return await org_service.get_org(current_user.organization_id)

@router.put("/my", response_model=OrganizationResponse)
async def update_my_org(
    request_data: OrganizationUpdate,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin", "SuperAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    org_service = OrganizationService(db)
    return await org_service.update_org(current_user.organization_id, request_data)

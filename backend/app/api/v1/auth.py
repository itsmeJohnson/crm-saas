from typing import Annotated
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import RegisterTenantRequest, LoginRequest, Token, RefreshTokenRequest, AuthMeResponse
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.schemas.user import UserResponse
from app.schemas.organization import OrganizationResponse

router = APIRouter()

@router.post("/register", response_model=AuthMeResponse)
async def register(
    request: RegisterTenantRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    user, org = await auth_service.register_tenant(request)
    return AuthMeResponse(
        user=UserResponse.model_validate(user),
        organization=OrganizationResponse.model_validate(org)
    )

@router.post("/login", response_model=Token)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(request_data)
    
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    return await auth_service.create_user_session(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/refresh", response_model=Token)
async def refresh(
    request_data: RefreshTokenRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    return await auth_service.refresh_session(
        refresh_token=request_data.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/logout")
async def logout(
    request_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    await auth_service.logout_session(request_data.refresh_token)
    return {"detail": "Logged out successfully"}

@router.get("/me", response_model=AuthMeResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    org_repo = OrganizationRepository(db)
    org = await org_repo.get(current_user.organization_id)
    return AuthMeResponse(
        user=UserResponse.model_validate(current_user),
        organization=OrganizationResponse.model_validate(org)
    )

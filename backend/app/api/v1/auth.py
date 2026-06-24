from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.schemas.auth import (
    RegisterTenantRequest, LoginRequest, Token, RefreshTokenRequest, 
    AuthMeResponse, ForgotPasswordRequest, ResetPasswordRequest
)
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.schemas.user import UserResponse
from app.schemas.organization import OrganizationResponse
from app.middleware.permissions import check_is_team_leader
from datetime import datetime, timedelta, timezone
import secrets

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
    # Check if they are a Team Leader and set it dynamically
    current_user.is_team_leader = await check_is_team_leader(current_user, db)

    # Fetch active features for user/organization
    from app.models.tenant_subscription import TenantSubscription
    from app.models.plan_feature import PlanFeature
    from app.models.feature import Feature

    feature_codes = []
    if current_user.role == "SuperAdmin":
        f_stmt = select(Feature.code).where(Feature.active == True, Feature.is_deleted == False)
        f_res = await db.execute(f_stmt)
        feature_codes = list(f_res.scalars().all())
    else:
        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == current_user.organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()
        if sub and sub.status in ["active", "trial"]:
            pf_stmt = (
                select(Feature.code)
                .join(PlanFeature, PlanFeature.feature_id == Feature.id)
                .where(
                    PlanFeature.plan_id == sub.plan_id,
                    PlanFeature.enabled == True,
                    Feature.active == True,
                    Feature.is_deleted == False
                )
            )
            pf_res = await db.execute(pf_stmt)
            feature_codes = list(pf_res.scalars().all())

    return AuthMeResponse(
        user=UserResponse.model_validate(current_user),
        organization=OrganizationResponse.model_validate(org),
        features=feature_codes
    )

@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Find user by email
    query = select(User).where(User.email == payload.email, User.is_deleted == False)
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user registered with this email address"
        )
    
    # Generate secure token and store its SHA-256 hash
    from app.core.security import generate_random_token, hash_token
    token = generate_random_token()
    hashed_token = hash_token(token)
    
    user.reset_token = hashed_token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    await db.commit()
    
    # Resolve frontend URL dynamically from config
    from app.core.config import settings
    frontend_url = "http://localhost:5173"
    if settings.BACKEND_CORS_ORIGINS:
        frontend_url = settings.BACKEND_CORS_ORIGINS[0]
    
    reset_url = f"{frontend_url}/login?token={token}"
    
    # Trigger email notification
    from app.services.email_service import send_email
    send_email(
        to_email=user.email,
        subject="Reset your TeleCRM Password",
        template_name="password_reset.html",
        context={"reset_url": reset_url}
    )
    
    return {
        "detail": "If your email is registered, you will receive a password reset link shortly."
    }

@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.core.security import hash_token, get_password_hash
    
    hashed_token = hash_token(payload.token)
    now = datetime.now(timezone.utc)
    query = select(User).where(
        User.reset_token == hashed_token,
        User.reset_token_expires > now,
        User.is_deleted == False
    )
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    user.hashed_password = get_password_hash(payload.password)
    user.reset_token = None
    user.reset_token_expires = None
    
    await db.commit()
    
    return {"detail": "Password has been reset successfully"}


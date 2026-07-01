from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.schemas.auth import (
    RegisterTenantRequest, LoginRequest, Token, RefreshTokenRequest,
    AuthMeResponse, ForgotPasswordRequest, ResetPasswordRequest,
    MFAVerifyRequest, MFASetupResponse, MFAEnableResponse, MFAStatusResponse
)
from app.services.auth_service import AuthService
from app.services.mfa_service import MFAService
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.schemas.user import UserResponse
from app.schemas.organization import OrganizationResponse
from app.middleware.permissions import check_is_team_leader, require_role
from datetime import datetime, timedelta, timezone
import secrets
import json

router = APIRouter()

# SuperAdmin-only dependency
_require_super_admin = require_role(["SuperAdmin"])

@router.post("/register", response_model=AuthMeResponse, status_code=201)
async def register(
    request: RegisterTenantRequest,
    actor: Annotated[User, Depends(_require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Create a new tenant organisation and its OrgAdmin user.
    Restricted to SuperAdmin — use the Admin Dashboard (/tenants) to onboard clients.
    """
    auth_service = AuthService(db)
    user, org = await auth_service.register_tenant(request)
    return AuthMeResponse(
        user=UserResponse.model_validate(user),
        organization=OrganizationResponse.model_validate(org)
    )


@router.post("/public-register", response_model=Token, status_code=201)
async def public_register(
    request: RegisterTenantRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Public self-serve signup. Always provisions a free trial (no payment taken),
    creates the OrgAdmin, and returns a session so the user is logged in immediately.
    Rate-limited by the auth-sensitive bucket in RateLimiterMiddleware.
    """
    # Force trial regardless of what the client sends — a public signup can never
    # self-provision a paid/active subscription without going through billing.
    request.is_trial = True

    auth_service = AuthService(db)
    from app.services.audit_service import AuditService
    audit = AuditService(db)

    user, org = await auth_service.register_tenant(request)

    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    tokens = await auth_service.create_user_session(
        user_id=user.id, ip_address=ip_address, user_agent=user_agent
    )
    await audit.log_event(
        actor_id=user.id,
        organization_id=org.id,
        event_type="AUTH_PUBLIC_SIGNUP",
        description=f"Public self-serve signup ({org.slug}) from {ip_address}",
        ip_address=ip_address,
        browser_info=user_agent,
    )
    return tokens

@router.post("/login", response_model=Token)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.services.audit_service import AuditService
    auth_service = AuthService(db)
    audit = AuditService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user = await auth_service.authenticate_user(request_data)
    except HTTPException:
        # Log failed login attempt (no user_id available)
        await audit.log_event(
            actor_id=None,
            organization_id=None,
            event_type="AUTH_LOGIN_FAILED",
            description=f"Failed login attempt for email: {request_data.email}",
            ip_address=ip_address,
            browser_info=user_agent,
        )
        raise

    # MFA check: if enabled, return a short-lived challenge token instead of full session
    if user.mfa_enabled:
        from app.core.security import create_mfa_challenge_token
        mfa_token = create_mfa_challenge_token(user.id)
        await audit.log_event(
            actor_id=user.id,
            organization_id=user.organization_id,
            event_type="AUTH_MFA_CHALLENGE",
            description=f"MFA challenge issued for login from {ip_address}",
            ip_address=ip_address,
            browser_info=user_agent,
        )
        return Token(
            access_token=mfa_token,
            refresh_token="",
            mfa_required=True
        )

    tokens = await auth_service.create_user_session(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    await audit.log_event(
        actor_id=user.id,
        organization_id=user.organization_id,
        event_type="AUTH_LOGIN",
        description=f"User logged in from {ip_address}",
        ip_address=ip_address,
        browser_info=user_agent,
    )
    return tokens

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
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.services.audit_service import AuditService
    auth_service = AuthService(db)
    await auth_service.logout_session(request_data.refresh_token)
    await AuditService(db).log_event(
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        event_type="AUTH_LOGOUT",
        description="User logged out",
    )
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
    # Always return the same response to prevent email enumeration
    GENERIC_RESPONSE = {"detail": "If your email is registered, you will receive a password reset link shortly."}

    # Find user by email
    query = select(User).where(User.email == payload.email, User.is_deleted == False)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user:
        # Return 200 with generic message — never reveal whether email exists
        return GENERIC_RESPONSE
    
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
    return GENERIC_RESPONSE

# ---------------------------------------------------------------------------
# MFA Endpoints
# ---------------------------------------------------------------------------

@router.get("/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get MFA status for the current user."""
    backup_remaining = 0
    if current_user.mfa_backup_codes:
        try:
            backup_remaining = len(json.loads(current_user.mfa_backup_codes))
        except Exception:
            backup_remaining = 0
    return MFAStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        backup_codes_remaining=backup_remaining
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Generate a new TOTP secret and QR code URI.
    User must scan with Google Authenticator and then call /mfa/enable to activate.
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=400,
            detail="MFA is already enabled. Disable it first before setting up again."
        )
    mfa_service = MFAService(db)
    result = await mfa_service.generate_setup(current_user.id)
    return MFASetupResponse(**result)


@router.post("/mfa/enable", response_model=MFAEnableResponse)
async def mfa_enable(
    payload: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Confirm MFA setup by verifying a TOTP code.
    Returns one-time backup codes — save them immediately.
    """
    if not payload.totp_code:
        raise HTTPException(status_code=400, detail="totp_code is required to enable MFA")
    mfa_service = MFAService(db)
    result = await mfa_service.enable_mfa(current_user.id, payload.totp_code)
    from app.services.audit_service import AuditService
    await AuditService(db).log_event(
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        event_type="AUTH_MFA_ENABLED",
        description="User enabled MFA",
    )
    return MFAEnableResponse(**result)


@router.post("/mfa/verify", response_model=Token)
async def mfa_verify(
    payload: MFAVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Complete the login MFA challenge.
    Send the mfa_token from the login response + either totp_code or backup_code.
    Returns full access + refresh tokens on success.
    """
    if not payload.mfa_token:
        raise HTTPException(status_code=400, detail="mfa_token is required")
    if not payload.totp_code and not payload.backup_code:
        raise HTTPException(status_code=400, detail="Either totp_code or backup_code is required")

    from app.core.security import decode_mfa_challenge_token
    user_id = decode_mfa_challenge_token(payload.mfa_token)

    mfa_service = MFAService(db)

    verified = False
    if payload.totp_code:
        verified = await mfa_service.verify_totp(user_id, payload.totp_code)
    if not verified and payload.backup_code:
        verified = await mfa_service.verify_backup_code(user_id, payload.backup_code)

    if not verified:
        from app.services.audit_service import AuditService
        await AuditService(db).log_event(
            actor_id=user_id,
            organization_id=None,
            event_type="AUTH_MFA_FAILED",
            description="Failed MFA verification attempt",
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code or backup code."
        )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    auth_service = AuthService(db)
    tokens = await auth_service.create_user_session(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    from app.services.audit_service import AuditService
    from app.repositories.user import UserRepository
    user = await UserRepository(db).get(user_id)
    await AuditService(db).log_event(
        actor_id=user_id,
        organization_id=user.organization_id if user else None,
        event_type="AUTH_LOGIN",
        description=f"User completed MFA and logged in from {ip_address}",
        ip_address=ip_address,
        browser_info=user_agent,
    )
    return tokens


@router.post("/mfa/disable")
async def mfa_disable(
    payload: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Disable MFA. Requires valid TOTP code or backup code."""
    mfa_service = MFAService(db)
    result = await mfa_service.disable_mfa(
        current_user.id,
        totp_code=payload.totp_code,
        backup_code=payload.backup_code
    )
    from app.services.audit_service import AuditService
    await AuditService(db).log_event(
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        event_type="AUTH_MFA_DISABLED",
        description="User disabled MFA",
    )
    return result


@router.post("/mfa/backup-codes/regenerate")
async def mfa_regenerate_backup_codes(
    payload: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Regenerate backup codes (requires valid TOTP). Old codes become invalid."""
    if not payload.totp_code:
        raise HTTPException(status_code=400, detail="totp_code is required")
    mfa_service = MFAService(db)
    return await mfa_service.regenerate_backup_codes(current_user.id, payload.totp_code)


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.core.security import hash_token, get_password_hash
    from app.services.audit_service import AuditService

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
    # Increment token_version to invalidate all existing sessions immediately
    user.token_version = (user.token_version or 1) + 1

    await db.commit()
    await AuditService(db).log_event(
        actor_id=user.id,
        organization_id=user.organization_id,
        event_type="AUTH_PASSWORD_RESET",
        description="Password reset completed — all existing sessions invalidated",
    )
    return {"detail": "Password has been reset successfully"}


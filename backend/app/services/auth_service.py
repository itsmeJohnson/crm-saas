from datetime import datetime, timedelta, timezone
from typing import Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.repositories.session import UserSessionRepository
from app.schemas.auth import RegisterTenantRequest, Token, LoginRequest
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.models.user import User
from app.models.organization import Organization
from app.core.config import settings

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.user_repo = UserRepository(db)
        self.session_repo = UserSessionRepository(db)

    async def register_tenant(self, request: RegisterTenantRequest) -> Tuple[User, Organization]:
        # Check slug exists
        existing_org = await self.org_repo.get_by_slug(request.slug)
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Organization slug already in use"
            )

        # Check email exists
        existing_user = await self.user_repo.get_by_email(request.admin_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )

        # Create organization
        org = await self.org_repo.create({
            "name": request.company_name,
            "slug": request.slug
        })

        # Create owner user
        hashed_password = get_password_hash(request.admin_password)
        user = await self.user_repo.create({
            "organization_id": org.id,
            "email": request.admin_email,
            "hashed_password": hashed_password,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "role": "OrgAdmin",
            "is_verified": True
        })

        return user, org

    async def authenticate_user(self, request: LoginRequest) -> User:
        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User account is deactivated"
            )
        return user

    async def create_user_session(self, user_id: Any, ip_address: str | None = None, user_agent: str | None = None) -> Token:
        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.session_repo.create({
            "user_id": user_id,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent
        })
        
        return Token(access_token=access_token, refresh_token=refresh_token)

    async def refresh_session(self, refresh_token: str, ip_address: str | None = None, user_agent: str | None = None) -> Token:
        session = await self.session_repo.get_by_refresh_token(refresh_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        # Rotate tokens: revoke current session
        await self.session_repo.revoke_session(session.id)
        
        # Check if the user is active
        user = await self.user_repo.get(session.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User account is inactive or not found"
            )

        # Create new tokens and new session
        return await self.create_user_session(session.user_id, ip_address, user_agent)

    async def logout_session(self, refresh_token: str) -> None:
        session = await self.session_repo.get_by_refresh_token(refresh_token)
        if session:
            await self.session_repo.revoke_session(session.id)

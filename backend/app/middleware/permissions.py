from typing import List, Annotated
from fastapi import Depends, HTTPException, status, Request
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
    from app.core.tenant_context import TenantContext
    TenantContext.set_tenant_id(current_user.organization_id)
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


async def resolve_feature_codes(user: User, db: AsyncSession) -> set:
    """Resolve the feature codes enabled for a user's tenant — identical logic
    to the /auth/me feature resolution. SuperAdmin gets every active feature."""
    from app.models.feature import Feature
    from app.models.plan_feature import PlanFeature
    from app.models.tenant_subscription import TenantSubscription
    from sqlalchemy import func
    from app.core.config import settings

    # Check if the feature catalog is completely empty (unseeded test database)
    feature_count_res = await db.execute(select(func.count(Feature.id)))
    feature_count = feature_count_res.scalar() or 0

    # SECURITY: this fallback grants ALL features and MUST be impossible outside the
    # explicit test environment. Gate on the positive settings.is_testing
    # (ENVIRONMENT == "testing") — never on a raw/negative env check — so it can never
    # activate in staging/production even if TESTING=true is present.
    if feature_count == 0 and settings.is_testing:
        return {
            "LEAD_MANAGEMENT", "CONTACT_MANAGEMENT", "FOLLOW_UP_TASKS",
            "SALES_PIPELINE", "CLICK_TO_CALL", "BASIC_DASHBOARD", "DASHBOARD_REPORTS",
            "BULK_IMPORT", "GOOGLE_SHEETS_IMPORT", "BULK_ASSIGNMENT",
            "ROLE_BASED_ACCESS", "CUSTOM_PIPELINE", "LEAD_DISTRIBUTION",
            "KPI_DASHBOARD", "TARGET_MANAGEMENT", "MANAGER_DASHBOARD", "TEAM_LEADER_DASHBOARD",
            "CALL_RECORDING", "INBOUND_CALLING", "OUTBOUND_CALLING",
            "SMS_MESSAGING", "EMAIL_MESSAGING", "WHATSAPP_MESSAGING", "CAMPAIGN_MANAGEMENT",
            "LEAD_CAPTURE", "ADVANCED_PIPELINE", "LEAD_TRANSFERS", "BULK_TRANSFER",
            "SMART_DISTRIBUTION", "TEAM_MONITORING", "CALL_DISPOSITION",
            "AI_CALL_SUMMARY", "AI_FOLLOW_UP", "ADVANCED_ANALYTICS",
            "CONVERSION_ANALYTICS", "CUSTOM_REPORTS", "PRIORITY_SUPPORT",
            "WHITE_LABEL", "API_ACCESS"
        }

    if user.role == "SuperAdmin":
        res = await db.execute(
            select(Feature.code).where(Feature.active == True, Feature.is_deleted == False)
        )
        return set(res.scalars().all())

    stmt = (
        select(Feature.code)
        .join(PlanFeature, PlanFeature.feature_id == Feature.id)
        .join(TenantSubscription, TenantSubscription.plan_id == PlanFeature.plan_id)
        .where(
            TenantSubscription.organization_id == user.organization_id,
            TenantSubscription.is_deleted == False,
            TenantSubscription.status.in_(["active", "trial"]),
            PlanFeature.enabled == True,
            Feature.active == True,
            Feature.is_deleted == False,
        )
    )
    res = await db.execute(stmt)
    return set(res.scalars().all())


def require_feature(feature_code: str):
    """Dependency factory: 403 unless the caller's plan includes `feature_code`.
    SuperAdmin bypasses. Server-side twin of the frontend FeatureGuardRoute so
    plan gating cannot be bypassed by calling the API directly."""
    async def dependency(
        current_user: Annotated[User, Depends(require_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if current_user.role == "SuperAdmin":
            return current_user
        codes = await resolve_feature_codes(current_user, db)
        if feature_code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your plan does not include this feature. Please upgrade to access it.",
            )
        return current_user
    return dependency

async def check_is_team_leader(user: User, db: AsyncSession) -> bool:
    """Check if the user is a Team Leader (Employee who reports to a Manager)."""
    if user.role != "Employee" or not user.reporting_to_id:
        return False
    parent_res = await db.execute(select(User.role).filter(User.id == user.reporting_to_id))
    parent_role = parent_res.scalar()
    return parent_role == "Manager"

def require_permission(resource: str, action: str):
    """Custom-role matrix check for a specific resource/action. No-ops for
    users without a custom_role_id — legacy role checks stay authoritative."""
    async def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ) -> User:
        from app.services.permission_service import PermissionService
        await PermissionService(db).require(current_user, resource, action)
        return current_user
    return dependency


_METHOD_ACTION = {"GET": "view", "POST": "create", "PATCH": "edit", "PUT": "edit", "DELETE": "delete"}


def enforce_resource(resource: str):
    """Router-level custom-role enforcement. Maps HTTP method (and well-known
    path suffixes: export/import/bulk/assign) to a matrix action. Runs after
    the endpoint's own legacy role dependency and only restricts users who
    carry a custom role, so existing behavior is unchanged for everyone else.
    Only attach to routers whose routes are all authenticated."""
    async def dependency(
        request: Request,
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ) -> None:
        if not current_user.custom_role_id or current_user.role == "SuperAdmin":
            return
        path = request.url.path
        action = _METHOD_ACTION.get(request.method, "view")
        if "/export" in path:
            action = "export"
        elif "/import" in path:
            action = "import"
        elif "/bulk" in path:
            action = "bulk"
        elif "/assign" in path or "/transfer" in path:
            action = "assign"
        from app.services.permission_service import PermissionService
        await PermissionService(db).require(current_user, resource, action)
    return dependency


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


class TelephonyAccessDenied(Exception):
    """Raised when a user may not access org telephony settings. An exception
    handler (main.py) renders it to the exact contract body at HTTP 403:
    {"success": false, "message": "You are not authorized to access telephony settings."}"""


async def require_manage_telephony(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Telephony settings are org-level and highly privileged. Allowed:
      - SuperAdmin (organization owner) — always
      - OrgAdmin — only if granted the 'integrations':'manage' permission
    Everyone else (Employee, Manager, TeamLeader, HR, custom roles, …) is denied.
    """
    if not current_user.is_active:
        raise TelephonyAccessDenied()
    if current_user.role == "SuperAdmin":
        return current_user
    if current_user.role == "OrgAdmin":
        from app.services.permission_service import PermissionService
        if await PermissionService(db).check(current_user, "integrations", "manage"):
            return current_user
    raise TelephonyAccessDenied()


def require_module(module_name: str):
    async def dependency(
        current_user: Annotated[User, Depends(require_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ) -> None:
        from app.core.industries import ALL_MODULES
        if module_name not in ALL_MODULES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for your organization"
            )
        if current_user.role == "SuperAdmin":
            return
        from app.services.tenant_config_service import TenantConfigurationResolver
        resolver = TenantConfigurationResolver(db)
        config = await resolver.resolve_config(current_user.organization_id)
        enabled_modules = config.get("enabled_modules", [])
        if module_name not in enabled_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for your organization"
            )
    return dependency

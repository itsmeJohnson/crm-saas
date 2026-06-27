import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate, UserUpdate, ReplaceEmployeeRequest, SeatUtilizationResponse, SeatHistoryResponse
from app.schemas.invitation import InvitationResponse, InvitationCreate, InvitationAccept
from app.services.user_service import UserService
from app.services.invitation_service import InvitationService
from app.middleware.permissions import require_active_user, require_role, require_user_management_permission, require_tl_or_above
from app.middleware.subscription_guard import check_user_creation_limit_dep, check_user_invite_limit_dep

router = APIRouter()

# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _limit_check: Annotated[None, Depends(check_user_creation_limit_dep)] = None
):
    """Create a new user within the organization."""
    user_service = UserService(db)
    return await user_service.create_user(actor, user_in.model_dump())

@router.get("/", response_model=List[UserResponse])
async def list_users(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=500),
    search: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None)
):
    """List paginated, searchable users scoped to the actor: org-wide for
    Manager/Admin, self + direct reports for Employees (TL or plain)."""
    user_service = UserService(db)
    records, _ = await user_service.paginate_users(actor, skip, limit, search, role, is_active)
    return list(records)

# ── Static paths MUST come before /{user_id} to avoid shadowing ──────────────

@router.get("/seat-utilization", response_model=SeatUtilizationResponse)
async def get_seat_utilization(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get the current seat licensing utilization metrics."""
    user_service = UserService(db)
    return await user_service.get_seat_utilization(actor.organization_id)

@router.get("/seat-history", response_model=List[SeatHistoryResponse])
async def get_seat_history(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get seat assignment and replacement history logs."""
    user_service = UserService(db)
    return await user_service.get_seat_history(actor.organization_id)

@router.get("/inactive-employees", response_model=List[UserResponse])
async def get_inactive_employees(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get a list of inactive employees who currently occupy a seat and can be replaced."""
    user_service = UserService(db)
    return await user_service.get_inactive_employees(actor.organization_id)

@router.post("/replace-employee", response_model=UserResponse)
async def replace_employee(
    request: Request,
    payload: ReplaceEmployeeRequest,
    actor: Annotated[User, Depends(require_user_management_permission())],
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response = None
):
    """Replace an inactive employee with a new employee, transferring their seat."""
    user_service = UserService(db)

    ip_address = request.client.host if request.client else None
    browser_info = request.headers.get("user-agent")

    new_user, notification = await user_service.replace_employee(
        actor=actor,
        old_user_id=payload.old_user_id,
        new_user_data=payload.model_dump(),
        ip_address=ip_address,
        browser_info=browser_info
    )

    if response:
        response.headers["X-Notification"] = notification

    return new_user

# ── Invitations ───────────────────────────────────────────────────────────────

@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    invite_in: InvitationCreate,
    actor: Annotated[User, Depends(require_user_management_permission())],
    db: Annotated[AsyncSession, Depends(get_db)],
    _limit_check: Annotated[None, Depends(check_user_invite_limit_dep)] = None
):
    """Invite a new user to the organization."""
    invite_service = InvitationService(db)
    return await invite_service.invite_user(actor, invite_in.email, invite_in.role)

@router.get("/invitations", response_model=List[InvitationResponse])
async def list_pending_invitations(
    actor: Annotated[User, Depends(require_user_management_permission())],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List pending user invitations in the tenant."""
    invite_service = InvitationService(db)
    records = await invite_service.get_pending_invites(actor)
    return list(records)

@router.post("/invitations/accept", response_model=UserResponse)
async def accept_invitation(
    accept_in: InvitationAccept,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Accept an invitation token to create and register user account."""
    invite_service = InvitationService(db)
    return await invite_service.accept_invite(
        token=accept_in.token,
        password=accept_in.password,
        first_name=accept_in.first_name,
        last_name=accept_in.last_name
    )

# ── User Detail Operations (/{user_id} MUST be last) ─────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed user profile scoped to organization."""
    user_service = UserService(db)
    return await user_service.get_user_by_id(actor, user_id)

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update profile or roles of a scoped user."""
    user_service = UserService(db)
    return await user_service.update_user(actor, user_id, user_in.model_dump(exclude_unset=True))

@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: uuid.UUID,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete user from the organization list."""
    user_service = UserService(db)
    return await user_service.soft_delete_user(actor, user_id)

@router.patch("/{user_id}/status", response_model=UserResponse)
async def toggle_user_status(
    user_id: uuid.UUID,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_active: bool = Query(...),
    inactive_reason: str | None = Query(None)
):
    """Activate or deactivate user account status."""
    user_service = UserService(db)
    return await user_service.toggle_active(actor, user_id, is_active, inactive_reason)

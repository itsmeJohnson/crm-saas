import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.activity import ActivityResponse, ActivityCreate, ActivityUpdate
from app.services.activity_service import ActivityService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    activity_in: ActivityCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new activity (event/task) for the organization."""
    activity_service = ActivityService(db)
    return await activity_service.create_activity(actor, activity_in.model_dump())

@router.get("/", response_model=List[ActivityResponse])
async def list_activities(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    activity_type: str | None = Query(None),
    status: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    lead_id: uuid.UUID | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    company_id: uuid.UUID | None = Query(None)
):
    """List paginated activities scoped to the tenant organization with optional filters."""
    activity_service = ActivityService(db)
    records, _ = await activity_service.paginate_activities(
        actor=actor,
        skip=skip,
        limit=limit,
        activity_type=activity_type,
        status_filter=status,
        assigned_user_id=assigned_user_id,
        lead_id=lead_id,
        contact_id=contact_id,
        company_id=company_id
    )
    return list(records)

@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed activity details scoped to organization."""
    activity_service = ActivityService(db)
    return await activity_service.get_activity(actor, activity_id)

@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: uuid.UUID,
    activity_in: ActivityUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped activity."""
    activity_service = ActivityService(db)
    return await activity_service.update_activity(actor, activity_id, activity_in.model_dump(exclude_unset=True))

@router.delete("/{activity_id}", response_model=ActivityResponse)
async def delete_activity(
    activity_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete activity from organization database."""
    activity_service = ActivityService(db)
    return await activity_service.soft_delete_activity(actor, activity_id)

import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.lead import LeadResponse, LeadCreate, LeadUpdate
from app.services.lead_service import LeadService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_in: LeadCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new lead opportunity."""
    lead_service = LeadService(db)
    return await lead_service.create_lead(actor, lead_in.model_dump())

@router.get("/", response_model=List[LeadResponse])
async def list_leads(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None)
):
    """List paginated, searchable leads scoped to the tenant organization."""
    lead_service = LeadService(db)
    records, _ = await lead_service.paginate_leads(
        actor, skip, limit, search, status, assigned_user_id
    )
    return list(records)

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed lead opportunity scoped to organization."""
    lead_service = LeadService(db)
    return await lead_service.get_lead(actor, lead_id)

@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    lead_in: LeadUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped lead opportunity."""
    lead_service = LeadService(db)
    return await lead_service.update_lead(actor, lead_id, lead_in.model_dump(exclude_unset=True))

@router.delete("/{lead_id}", response_model=LeadResponse)
async def delete_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete lead from organization database."""
    lead_service = LeadService(db)
    return await lead_service.soft_delete_lead(actor, lead_id)

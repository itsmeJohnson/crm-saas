import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.contact import ContactResponse, ContactCreate, ContactUpdate
from app.services.contact_service import ContactService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_in: ContactCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new contact linkable to a company."""
    contact_service = ContactService(db)
    return await contact_service.create_contact(actor, contact_in.model_dump())

@router.get("/", response_model=List[ContactResponse])
async def list_contacts(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    company_id: uuid.UUID | None = Query(None)
):
    """List paginated, searchable contacts scoped to the organization."""
    contact_service = ContactService(db)
    records, _ = await contact_service.paginate_contacts(actor, skip, limit, search, company_id)
    return list(records)

@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed contact profile scoped to organization."""
    contact_service = ContactService(db)
    return await contact_service.get_contact(actor, contact_id)

@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    contact_in: ContactUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped contact."""
    contact_service = ContactService(db)
    return await contact_service.update_contact(actor, contact_id, contact_in.model_dump(exclude_unset=True))

@router.delete("/{contact_id}", response_model=ContactResponse)
async def delete_contact(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete contact from organization database."""
    contact_service = ContactService(db)
    return await contact_service.soft_delete_contact(actor, contact_id)

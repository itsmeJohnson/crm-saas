import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.note import NoteResponse, NoteCreate, NoteUpdate
from app.services.note_service import NoteService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_in: NoteCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new note for the organization attached to a lead, contact, or company."""
    note_service = NoteService(db)
    return await note_service.create_note(actor, note_in.model_dump())

@router.get("/", response_model=List[NoteResponse])
async def list_notes(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    lead_id: uuid.UUID | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    company_id: uuid.UUID | None = Query(None)
):
    """List paginated notes scoped to the tenant organization with optional entity filters."""
    note_service = NoteService(db)
    records, _ = await note_service.paginate_notes(
        actor=actor,
        skip=skip,
        limit=limit,
        lead_id=lead_id,
        contact_id=contact_id,
        company_id=company_id
    )
    return list(records)

@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    note_in: NoteUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update content of a scoped note."""
    note_service = NoteService(db)
    return await note_service.update_note(actor, note_id, note_in.model_dump(exclude_unset=True))

@router.delete("/{note_id}", response_model=NoteResponse)
async def delete_note(
    note_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete note from organization database."""
    note_service = NoteService(db)
    return await note_service.soft_delete_note(actor, note_id)

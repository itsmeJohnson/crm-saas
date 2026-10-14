import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.email_sequence_service import EmailSequenceService
from app.schemas.email_sequence import (
    EmailSequenceCreate, EmailSequenceUpdate, EmailSequenceResponse,
    EnrollRequest, EnrollmentResponse,
)

router = APIRouter()


@router.get("", response_model=List[EmailSequenceResponse])
async def list_sequences(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).list_sequences(actor)


@router.post("", response_model=EmailSequenceResponse, status_code=status.HTTP_201_CREATED)
async def create_sequence(req: EmailSequenceCreate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).create_sequence(actor, req.model_dump())


@router.get("/{seq_id}", response_model=EmailSequenceResponse)
async def get_sequence(seq_id: uuid.UUID,
                       actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).get_sequence(actor, seq_id)


@router.patch("/{seq_id}", response_model=EmailSequenceResponse)
async def update_sequence(seq_id: uuid.UUID, req: EmailSequenceUpdate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).update_sequence(actor, seq_id, req.model_dump(exclude_unset=True))


@router.delete("/{seq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(seq_id: uuid.UUID,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    await EmailSequenceService(db).delete_sequence(actor, seq_id)


@router.get("/{seq_id}/enrollments", response_model=List[EnrollmentResponse])
async def list_enrollments(seq_id: uuid.UUID,
                           actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).list_enrollments(actor, seq_id)


@router.post("/{seq_id}/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_lead(seq_id: uuid.UUID, req: EnrollRequest,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await EmailSequenceService(db).enroll(actor, seq_id, req.lead_id)


@router.delete("/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_enrollment(enrollment_id: uuid.UUID,
                            actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    await EmailSequenceService(db).cancel_enrollment(actor, enrollment_id)

import uuid
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.note_repository import NoteRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.company_repository import CompanyRepository
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.note import Note

class NoteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.note_repo = NoteRepository(db)
        self.lead_repo = LeadRepository(db)
        self.contact_repo = ContactRepository(db)
        self.company_repo = CompanyRepository(db)
        self.audit_service = AuditService(db)

    async def get_note(self, actor: User, note_id: uuid.UUID) -> Note:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        note = await self.note_repo.get_note_by_id(actor.organization_id, note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return note

    async def _validate_references(self, organization_id: uuid.UUID, data: dict):
        lead_id = data.get("lead_id")
        if lead_id:
            lead = await self.lead_repo.get_lead_by_id(organization_id, lead_id)
            if not lead:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Lead not found in your organization"
                )

        contact_id = data.get("contact_id")
        if contact_id:
            contact = await self.contact_repo.get_contact_by_id(organization_id, contact_id)
            if not contact:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contact not found in your organization"
                )

        company_id = data.get("company_id")
        if company_id:
            company = await self.company_repo.get_company_by_id(organization_id, company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company not found in your organization"
                )

    async def create_note(self, actor: User, note_data: dict) -> Note:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Verify that note is linked to at least one entity
        if not any([note_data.get("lead_id"), note_data.get("contact_id"), note_data.get("company_id")]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Note must be linked to at least one entity (lead, contact, or company)"
            )

        await self._validate_references(actor.organization_id, note_data)

        note = await self.note_repo.create_note(actor.organization_id, note_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="NOTE_CREATED",
            resource_type="note",
            resource_id=str(note.id)
        )
        return note

    async def paginate_notes(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        lead_id: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[Note], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        if lead_id:
            lead = await self.lead_repo.get_lead_by_id(actor.organization_id, lead_id)
            if not lead:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead not found")

        if contact_id:
            contact = await self.contact_repo.get_contact_by_id(actor.organization_id, contact_id)
            if not contact:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact not found")

        if company_id:
            company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
            if not company:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company not found")

        return await self.note_repo.paginate_notes(
            organization_id=actor.organization_id,
            skip=skip,
            limit=limit,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id
        )

    async def update_note(self, actor: User, note_id: uuid.UUID, note_data: dict) -> Note:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        await self.get_note(actor, note_id)
        # Note content changes don't update reference links, but let's check validation checks
        updated = await self.note_repo.update_note(actor.organization_id, note_id, note_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="NOTE_UPDATED",
            resource_type="note",
            resource_id=str(note_id)
        )
        return updated

    async def soft_delete_note(self, actor: User, note_id: uuid.UUID) -> Note:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        await self.get_note(actor, note_id)

        deleted = await self.note_repo.soft_delete_note(actor.organization_id, note_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="NOTE_DELETED",
            resource_type="note",
            resource_id=str(note_id)
        )
        return deleted

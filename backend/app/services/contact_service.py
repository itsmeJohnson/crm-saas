import uuid
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.contact_repository import ContactRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.contact import Contact

class ContactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.contact_repo = ContactRepository(db)
        self.company_repo = CompanyRepository(db)
        self.user_repo = UserRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.note_repo = NoteRepository(db)
        self.audit_service = AuditService(db)

    async def get_contact(self, actor: User, contact_id: uuid.UUID) -> Contact:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        contact = await self.contact_repo.get_contact_by_id(actor.organization_id, contact_id)
        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        return contact

    async def create_contact(self, actor: User, contact_data: dict) -> Contact:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Validate company reference
        company_id = contact_data.get("company_id")
        if company_id:
            company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company not found in your organization"
                )

        # Validate assigned user organization
        assigned_user_id = contact_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        contact = await self.contact_repo.create_contact(actor.organization_id, contact_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CONTACT_CREATED",
            resource_type="contact",
            resource_id=str(contact.id),
            action_metadata={"email": contact.email, "name": f"{contact.first_name} {contact.last_name}"}
        )
        return contact

    async def paginate_contacts(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        company_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[Contact], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        if company_id:
            # Verify company belongs to tenant
            company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company not found in your organization"
                )

        return await self.contact_repo.paginate_contacts(actor.organization_id, skip, limit, search_query, company_id)

    async def update_contact(self, actor: User, contact_id: uuid.UUID, contact_data: dict) -> Contact:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        contact = await self.get_contact(actor, contact_id)

        # Validate company reference if updated
        company_id = contact_data.get("company_id")
        if company_id:
            company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company not found in your organization"
                )

        # Validate assigned user organization if updated
        assigned_user_id = contact_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        updated = await self.contact_repo.update_contact(actor.organization_id, contact_id, contact_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CONTACT_UPDATED",
            resource_type="contact",
            resource_id=str(contact_id),
            action_metadata={"updated_fields": list(contact_data.keys())}
        )
        return updated

    async def soft_delete_contact(self, actor: User, contact_id: uuid.UUID) -> Contact:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        contact = await self.get_contact(actor, contact_id)

        deleted = await self.contact_repo.soft_delete_contact(actor.organization_id, contact_id)

        # Cascade soft-delete activities and notes
        await self.activity_repo.soft_delete_by_parent(actor.organization_id, "contact", contact_id)
        await self.note_repo.soft_delete_by_parent(actor.organization_id, "contact", contact_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CONTACT_DELETED",
            resource_type="contact",
            resource_id=str(contact_id)
        )
        return deleted

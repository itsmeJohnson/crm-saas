import uuid
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.company import Company

class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.company_repo = CompanyRepository(db)
        self.user_repo = UserRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.note_repo = NoteRepository(db)
        self.audit_service = AuditService(db)

    async def get_company(self, actor: User, company_id: uuid.UUID) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        return company

    async def create_company(self, actor: User, company_data: dict) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Validate assigned user organization
        assigned_user_id = company_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        company = await self.company_repo.create_company(actor.organization_id, company_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_CREATED",
            resource_type="company",
            resource_id=str(company.id),
            action_metadata={"name": company.name}
        )
        return company

    async def paginate_companies(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None
    ) -> Tuple[Sequence[Company], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        return await self.company_repo.paginate_companies(actor.organization_id, skip, limit, search_query)

    async def update_company(self, actor: User, company_id: uuid.UUID, company_data: dict) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        company = await self.get_company(actor, company_id)

        # Validate assigned user organization
        assigned_user_id = company_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        updated = await self.company_repo.update_company(actor.organization_id, company_id, company_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_UPDATED",
            resource_type="company",
            resource_id=str(company_id),
            action_metadata={"updated_fields": list(company_data.keys())}
        )
        return updated

    async def soft_delete_company(self, actor: User, company_id: uuid.UUID) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        company = await self.get_company(actor, company_id)

        # Soft delete company
        deleted = await self.company_repo.soft_delete_company(actor.organization_id, company_id)

        # Cascade soft-delete activities and notes
        await self.activity_repo.soft_delete_by_parent(actor.organization_id, "company", company_id)
        await self.note_repo.soft_delete_by_parent(actor.organization_id, "company", company_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_DELETED",
            resource_type="company",
            resource_id=str(company_id)
        )
        return deleted

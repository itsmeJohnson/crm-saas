import uuid
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.lead_repository import LeadRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository
from app.services.audit_service import AuditService
from app.services.dashboard_service import DashboardService
from app.models.user import User
from app.models.lead import Lead

class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.user_repo = UserRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.note_repo = NoteRepository(db)
        self.audit_service = AuditService(db)

    async def get_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.lead_repo.get_lead_by_id(actor.organization_id, lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            from app.services.user_service import UserService
            user_service = UserService(self.db)
            downline_ids = await user_service.get_downline_user_ids(actor)
            allowed_user_ids = downline_ids | {actor.id}
            if lead.assigned_user_id not in allowed_user_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

        return lead

    async def create_lead(self, actor: User, lead_data: dict) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Validate assigned user organization
        assigned_user_id = lead_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        lead = await self.lead_repo.create_lead(actor.organization_id, lead_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_CREATED",
            resource_type="lead",
            resource_id=str(lead.id),
            action_metadata={"title": lead.title, "status": lead.status}
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return lead

    async def paginate_leads(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        status_filter: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        name: str | None = None,
        city: str | None = None
    ) -> Tuple[Sequence[Lead], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Org-wide visibility for admins/managers; everyone else is scoped to
        # themselves plus their recursive downline (so a telecaller only sees
        # their own leads, and a team lead sees their own + their team's).
        allowed_user_ids: set[uuid.UUID] | None = None
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            from app.services.user_service import UserService
            user_service = UserService(self.db)
            downline_ids = await user_service.get_downline_user_ids(actor)
            allowed_user_ids = downline_ids | {actor.id}

        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found in your organization"
                )
            if allowed_user_ids is not None and assigned_user_id not in allowed_user_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Assigned user is not yourself or in your downline reporting chain"
                )

        return await self.lead_repo.paginate_leads(
            actor.organization_id, skip, limit, search_query, status_filter, assigned_user_id, name, city,
            allowed_user_ids
        )

    async def update_lead(self, actor: User, lead_id: uuid.UUID, lead_data: dict) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.get_lead(actor, lead_id)

        # Validate assigned user organization if updated
        assigned_user_id = lead_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        updated = await self.lead_repo.update_lead(actor.organization_id, lead_id, lead_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_UPDATED",
            resource_type="lead",
            resource_id=str(lead_id),
            action_metadata={"updated_fields": list(lead_data.keys())}
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return updated

    async def soft_delete_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.get_lead(actor, lead_id)

        deleted = await self.lead_repo.soft_delete_lead(actor.organization_id, lead_id)

        # Cascade soft-delete activities and notes
        await self.activity_repo.soft_delete_by_parent(actor.organization_id, "lead", lead_id)
        await self.note_repo.soft_delete_by_parent(actor.organization_id, "lead", lead_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_DELETED",
            resource_type="lead",
            resource_id=str(lead_id)
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return deleted

import uuid
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.activity_repository import ActivityRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.activity import Activity

class ActivityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_repo = ActivityRepository(db)
        self.lead_repo = LeadRepository(db)
        self.contact_repo = ContactRepository(db)
        self.company_repo = CompanyRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def get_activity(self, actor: User, activity_id: uuid.UUID) -> Activity:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        activity = await self.activity_repo.get_activity_by_id(actor.organization_id, activity_id)
        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
        return activity

    async def _validate_references(self, organization_id: uuid.UUID, data: dict):
        # Validate lead
        lead_id = data.get("lead_id")
        if lead_id:
            lead = await self.lead_repo.get_lead_by_id(organization_id, lead_id)
            if not lead:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Lead not found in your organization"
                )

        # Validate contact
        contact_id = data.get("contact_id")
        if contact_id:
            contact = await self.contact_repo.get_contact_by_id(organization_id, contact_id)
            if not contact:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contact not found in your organization"
                )

        # Validate company
        company_id = data.get("company_id")
        if company_id:
            company = await self.company_repo.get_company_by_id(organization_id, company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company not found in your organization"
                )

        # Validate assigned user
        assigned_user_id = data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

    async def create_activity(self, actor: User, activity_data: dict) -> Activity:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        await self._validate_references(actor.organization_id, activity_data)

        activity = await self.activity_repo.create_activity(actor.organization_id, activity_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="ACTIVITY_CREATED",
            resource_type="activity",
            resource_id=str(activity.id),
            action_metadata={"subject": activity.subject, "activity_type": activity.activity_type}
        )
        return activity

    async def paginate_activities(
        self, 
        actor: User, 
        skip: int = 0, 
        limit: int = 100, 
        activity_type: str | None = None,
        status_filter: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[Activity], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Verify query filters belong to organization
        if assigned_user_id:
            user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user not found")

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

        return await self.activity_repo.paginate_activities(
            organization_id=actor.organization_id,
            skip=skip,
            limit=limit,
            activity_type=activity_type,
            status=status_filter,
            assigned_user_id=assigned_user_id,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id
        )

    async def update_activity(self, actor: User, activity_id: uuid.UUID, activity_data: dict) -> Activity:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        await self.get_activity(actor, activity_id)
        await self._validate_references(actor.organization_id, activity_data)

        updated = await self.activity_repo.update_activity(actor.organization_id, activity_id, activity_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="ACTIVITY_UPDATED",
            resource_type="activity",
            resource_id=str(activity_id),
            action_metadata={"updated_fields": list(activity_data.keys())}
        )
        return updated

    async def soft_delete_activity(self, actor: User, activity_id: uuid.UUID) -> Activity:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        await self.get_activity(actor, activity_id)

        deleted = await self.activity_repo.soft_delete_activity(actor.organization_id, activity_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="ACTIVITY_DELETED",
            resource_type="activity",
            resource_id=str(activity_id)
        )
        return deleted

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.schemas.lead_assign import LeadBulkAssignRequest, LeadBulkAssignResponse
from app.services.user_service import UserService
from app.models.lead import Lead
from app.models.user import User
from app.models.assignment_config import AssignmentConfig
from app.repositories.assignment_config_repository import AssignmentConfigRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService

class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_repo = AssignmentConfigRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    async def get_or_create_config(self, organization_id: uuid.UUID) -> AssignmentConfig:
        """Fetch assignment configuration for organization, creating it if not present."""
        # Use with_for_update to lock config row during retrieval to prevent race conditions
        query = select(AssignmentConfig).filter(
            AssignmentConfig.organization_id == organization_id
        ).with_for_update()
        result = await self.db.execute(query)
        config = result.scalars().first()

        if not config:
            config = await self.config_repo.create({
                "organization_id": organization_id,
                "is_active": True,
                "last_assigned_user_id": None
            })
        return config

    async def toggle_assignment(self, organization_id: uuid.UUID, is_active: bool) -> AssignmentConfig:
        """Update auto-assignment active status."""
        config = await self.get_or_create_config(organization_id)
        updated = await self.config_repo.update(config, {"is_active": is_active})
        return updated

    async def assign_lead(self, lead: Lead) -> User | None:
        """
        Auto-assign a Lead to an active Employee user via round-robin.
        Returns the assigned User, or None if assignment is disabled or no users are active.
        """
        config = await self.get_or_create_config(lead.organization_id)
        if not config.is_active:
            return None

        # Fetch active Employees sorted by ID to maintain a persistent queue order
        user_query = select(User).filter(
            User.organization_id == lead.organization_id,
            User.role == "Employee",
            User.is_active == True,
            User.is_deleted == False
        ).order_by(User.id)
        result = await self.db.execute(user_query)
        active_employees = result.scalars().all()

        if not active_employees:
            return None

        # Determine index of the next assignee
        next_user = active_employees[0]
        if config.last_assigned_user_id:
            try:
                last_index = next(
                    i for i, u in enumerate(active_employees) 
                    if u.id == config.last_assigned_user_id
                )
                next_index = (last_index + 1) % len(active_employees)
                next_user = active_employees[next_index]
            except StopIteration:
                # Last assigned user is no longer active/present, fall back to first user
                next_user = active_employees[0]

        # Apply assignment
        lead.assigned_user_id = next_user.id
        config.last_assigned_user_id = next_user.id
        self.db.add(lead)
        self.db.add(config)
        await self.db.flush()

        # Log audit entry
        await self.audit_service.log_event(
            organization_id=lead.organization_id,
            actor_user_id=lead.created_by,
            action="LEAD_ASSIGNED",
            resource_type="lead",
            resource_id=str(lead.id),
            action_metadata={
                "assigned_user_id": str(next_user.id),
                "assigned_email": next_user.email,
                "reason": "auto_assignment"
            }
        )

        return next_user

    async def assign_lead_to_user(self, lead: Lead, user: User) -> None:
        """
        Manually assign a Lead to a specific active Employee user.
        """
        lead.assigned_user_id = user.id
        self.db.add(lead)
        await self.db.flush()

        # Log audit entry
        await self.audit_service.log_event(
            organization_id=lead.organization_id,
            actor_user_id=lead.created_by,
            action="LEAD_ASSIGNED",
            resource_type="lead",
            resource_id=str(lead.id),
            action_metadata={
                "assigned_user_id": str(user.id),
                "assigned_email": user.email,
                "reason": "specific_assignment"
            }
        )

    async def assign_leads_bulk(self, actor: User, req: LeadBulkAssignRequest) -> LeadBulkAssignResponse:
        """
        Bulk assign leads to a list of downline users using a SPLIT or RANGE strategy.
        Locks rows in the database (FOR UPDATE) to prevent race conditions.
        """
        # 1. Verify all assignee_ids are downlines of actor
        user_service = UserService(self.db)
        downline_ids = await user_service.get_downline_user_ids(actor)
        
        # Check if caller has downlines and assignees are valid downlines
        for assignee_id in req.assignee_ids:
            if assignee_id not in downline_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User {assignee_id} is not in your downline reporting chain"
                )

        # 2. Fetch assignees to verify active status
        assignees_query = select(User).filter(
            User.id.in_(req.assignee_ids),
            User.is_deleted == False,
            User.is_active == True
        )
        assignees_res = await self.db.execute(assignees_query)
        assignees = {u.id: u for u in assignees_res.scalars().all()}
        
        # Verify all assignee_ids are active, valid users
        for assignee_id in req.assignee_ids:
            if assignee_id not in assignees:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Assignee {assignee_id} is inactive, deleted, or does not exist"
                )

        # 3. Fetch leads with FOR UPDATE row locking
        if req.lead_ids is not None:
            leads_query = select(Lead).filter(
                Lead.id.in_(req.lead_ids),
                Lead.organization_id == actor.organization_id
            ).with_for_update().order_by(Lead.id)
        elif req.import_id is not None:
            leads_query = select(Lead).filter(
                Lead.import_id == req.import_id,
                Lead.organization_id == actor.organization_id
            ).with_for_update().order_by(Lead.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either lead_ids or import_id must be provided"
            )

        leads_res = await self.db.execute(leads_query)
        leads = list(leads_res.scalars().all())

        if not leads:
            return LeadBulkAssignResponse(
                assigned_count=0,
                lead_ids=[],
                assignee_ids=req.assignee_ids
            )

        # 4. Optional Index Slicing
        start = req.range_start if req.range_start is not None else 0
        end = req.range_end if req.range_end is not None else len(leads)
        
        sliced_leads = leads[start:end]
        
        if not sliced_leads:
            return LeadBulkAssignResponse(
                assigned_count=0,
                lead_ids=[],
                assignee_ids=req.assignee_ids
            )

        num_leads = len(sliced_leads)
        num_assignees = len(req.assignee_ids)

        # 5. Distribute leads according to strategy
        assigned_lead_ids = []
        if req.strategy == "SPLIT":
            # Divide into contiguous chunks
            k = num_leads // num_assignees
            r = num_leads % num_assignees
            
            idx = 0
            for i, assignee_id in enumerate(req.assignee_ids):
                chunk_size = k + (1 if i < r else 0)
                for _ in range(chunk_size):
                    lead = sliced_leads[idx]
                    lead.assigned_user_id = assignee_id
                    self.db.add(lead)
                    assigned_lead_ids.append(lead.id)
                    idx += 1
                    
        elif req.strategy == "RANGE":
            # Distribute interleaved (round-robin)
            for idx, lead in enumerate(sliced_leads):
                assignee_id = req.assignee_ids[idx % num_assignees]
                lead.assigned_user_id = assignee_id
                self.db.add(lead)
                assigned_lead_ids.append(lead.id)

        # 6. Flush changes
        await self.db.flush()

        # Log audit logs for each assigned lead
        for lead in sliced_leads:
            assignee = assignees[lead.assigned_user_id]
            await self.audit_service.log_event(
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                action="LEAD_ASSIGNED",
                resource_type="lead",
                resource_id=str(lead.id),
                action_metadata={
                    "assigned_user_id": str(assignee.id),
                    "assigned_email": assignee.email,
                    "reason": "bulk_assignment",
                    "strategy": req.strategy
                }
            )

        return LeadBulkAssignResponse(
            assigned_count=len(assigned_lead_ids),
            lead_ids=assigned_lead_ids,
            assignee_ids=req.assignee_ids
        )

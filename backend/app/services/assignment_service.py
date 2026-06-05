import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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

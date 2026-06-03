import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.audit_repository import AuditRepository
from app.models.audit_log import AuditLog

class AuditService:
    def __init__(self, db: AsyncSession):
        self.audit_repo = AuditRepository(db)

    async def log_event(
        self,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        action_metadata: dict | None = None
    ) -> AuditLog:
        """
        Log an audit event with standard layout and fields.
        Standard action names:
        - USER_CREATED
        - USER_UPDATED
        - USER_DEACTIVATED
        - USER_ACTIVATED
        - USER_DELETED
        - INVITE_CREATED
        - INVITE_REVOKED
        - INVITE_ACCEPTED
        """
        log_data = {
            "actor_user_id": actor_user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action_metadata": action_metadata
        }
        return await self.audit_repo.create_log(organization_id, log_data)

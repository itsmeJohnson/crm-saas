import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.audit_repository import AuditRepository
from app.models.audit_log import AuditLog

class AuditService:
    def __init__(self, db: AsyncSession):
        self.audit_repo = AuditRepository(db)

    async def log_event(
        self,
        organization_id: uuid.UUID | None,
        actor_user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str = "Auth",
        resource_id: str | None = None,
        action_metadata: dict | None = None,
        *,
        actor_id: uuid.UUID | None = None,
        event_type: str | None = None,
        description: str | None = None,
        ip_address: str | None = None,
        browser_info: str | None = None,
    ) -> AuditLog | None:
        """
        Log an audit event. Silently skips if organization_id is None
        (e.g. SuperAdmin system-level actions have no tenant org).
        Standard action names:
        - USER_CREATED, USER_UPDATED, USER_DEACTIVATED, USER_ACTIVATED
        - USER_DELETED, INVITE_CREATED, INVITE_REVOKED, INVITE_ACCEPTED

        Accepts both the (actor_user_id, action, resource_type, resource_id,
        action_metadata) calling convention and the auth-flow convention
        (actor_id, event_type, description, ip_address, browser_info) -
        the latter is folded into action/action_metadata.
        """
        if organization_id is None:
            return None
        resolved_actor = actor_user_id if actor_user_id is not None else actor_id
        resolved_action = action or event_type
        metadata = dict(action_metadata or {})
        if description is not None:
            metadata["description"] = description
        if ip_address is not None:
            metadata["ip_address"] = ip_address
        if browser_info is not None:
            metadata["browser_info"] = browser_info
        log_data = {
            "actor_user_id": resolved_actor,
            "action": resolved_action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action_metadata": metadata or None
        }
        return await self.audit_repo.create_log(organization_id, log_data)

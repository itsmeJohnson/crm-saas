import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_object import CustomObjectDefinition, CustomObjectRecord
from app.models.user import User
from app.services.audit_service import AuditService
from app.core.reserved_fields import is_reserved_object_key


class CustomObjectService:
    """Manage tenant custom-object DEFINITIONS. Records are handled by
    CustomObjectRecordService. Always org-scoped; admin-gated for writes."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _ensure_admin(self, actor: User) -> None:
        if actor.role not in ("OrgAdmin", "SuperAdmin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can manage custom objects.",
            )

    async def list_objects(self, actor: User, include_inactive: bool = False) -> list[CustomObjectDefinition]:
        q = select(CustomObjectDefinition).filter(
            CustomObjectDefinition.organization_id == actor.organization_id,
            CustomObjectDefinition.is_deleted == False,
        )
        if not include_inactive:
            q = q.filter(CustomObjectDefinition.is_active == True)
        q = q.order_by(CustomObjectDefinition.created_at.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_by_key(self, actor: User, key: str) -> CustomObjectDefinition:
        res = await self.db.execute(
            select(CustomObjectDefinition).filter(
                CustomObjectDefinition.organization_id == actor.organization_id,
                CustomObjectDefinition.key == key,
                CustomObjectDefinition.is_deleted == False,
            )
        )
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom object not found")
        return obj

    async def _get_owned(self, actor: User, object_id: uuid.UUID) -> CustomObjectDefinition:
        res = await self.db.execute(
            select(CustomObjectDefinition).filter(
                CustomObjectDefinition.id == object_id,
                CustomObjectDefinition.organization_id == actor.organization_id,
                CustomObjectDefinition.is_deleted == False,
            )
        )
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom object not found")
        return obj

    async def create_object(self, actor: User, data: dict) -> CustomObjectDefinition:
        self._ensure_admin(actor)
        key = data["key"]
        if is_reserved_object_key(key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Object key '{key}' is reserved and cannot be used.",
            )
        # Unique per org (case-insensitive on the machine key).
        existing = await self.db.execute(
            select(CustomObjectDefinition.id).filter(
                CustomObjectDefinition.organization_id == actor.organization_id,
                CustomObjectDefinition.key == key,
                CustomObjectDefinition.is_deleted == False,
            )
        )
        if existing.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A custom object with key '{key}' already exists.",
            )
        obj = CustomObjectDefinition(
            organization_id=actor.organization_id,
            key=key,
            label=data["label"],
            label_plural=data.get("label_plural"),
            description=data.get("description"),
            icon=data.get("icon"),
            color=data.get("color"),
            display_field_key=data.get("display_field_key"),
            created_by=actor.id,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_CREATED", resource_type="custom_object_definition",
            resource_id=str(obj.id), action_metadata={"key": obj.key, "label": obj.label},
        )
        return obj

    async def update_object(self, actor: User, object_id: uuid.UUID, data: dict) -> CustomObjectDefinition:
        self._ensure_admin(actor)
        obj = await self._get_owned(actor, object_id)
        for k, v in data.items():
            setattr(obj, k, v)
        obj.updated_by = actor.id
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_UPDATED", resource_type="custom_object_definition",
            resource_id=str(obj.id), action_metadata={"key": obj.key},
        )
        return obj

    async def delete_object(self, actor: User, object_id: uuid.UUID) -> None:
        """Soft-delete an object definition. BLOCKED while live records exist
        (approved decision: never cascade-delete tenant records)."""
        self._ensure_admin(actor)
        obj = await self._get_owned(actor, object_id)
        record_count = (await self.db.execute(
            select(func.count(CustomObjectRecord.id)).filter(
                CustomObjectRecord.organization_id == actor.organization_id,
                CustomObjectRecord.object_definition_id == obj.id,
                CustomObjectRecord.is_deleted == False,
            )
        )).scalar() or 0
        if record_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete object '{obj.label}': it still has {record_count} record(s). "
                       f"Delete the records first.",
            )
        obj.is_deleted = True
        obj.is_active = False
        self.db.add(obj)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_DELETED", resource_type="custom_object_definition",
            resource_id=str(obj.id), action_metadata={"key": obj.key},
        )

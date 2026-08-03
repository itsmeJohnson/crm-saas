import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_field_definition import CustomFieldDefinition
from app.models.user import User
from app.services.metadata_cache_service import MetadataCacheService
from app.services.audit_service import AuditService


class CustomFieldService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)

    def _ensure_admin(self, actor: User) -> None:
        """Enforces that only OrgAdmin or SuperAdmin roles can manage metadata configurations."""
        if actor.role not in ("OrgAdmin", "SuperAdmin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can manage metadata configurations."
            )

    async def list_definitions(self, actor: User, entity_type: str = "contact") -> list[CustomFieldDefinition]:
        # Access through cache first
        # Convert cache mapping list of dicts to instances for repository compatibility
        cached = await MetadataCacheService.get_custom_fields(actor.organization_id, entity_type)
        if cached is not None:
            return [
                CustomFieldDefinition(
                    id=uuid.UUID(d["id"]),
                    organization_id=actor.organization_id,
                    entity_type=d["entity_type"],
                    key=d["key"],
                    label=d["label"],
                    field_type=d["field_type"],
                    options=d.get("options"),
                    placeholder=d.get("placeholder"),
                    description=d.get("description"),
                    default_value=d.get("default_value"),
                    validation_rules=d.get("validation_rules"),
                    section=d.get("section"),
                    is_active=d.get("is_active", True),
                    read_only=d.get("read_only", False),
                    visible=d.get("visible", True),
                    searchable=d.get("searchable", True),
                    filterable=d.get("filterable", True),
                    exportable=d.get("exportable", True),
                    importable=d.get("importable", True)
                )
                for d in cached
            ]

        res = await self.db.execute(
            select(CustomFieldDefinition).filter(
                CustomFieldDefinition.organization_id == actor.organization_id,
                CustomFieldDefinition.entity_type == entity_type,
                CustomFieldDefinition.is_deleted == False,
            ).order_by(CustomFieldDefinition.created_at.asc())
        )
        definitions = list(res.scalars().all())

        # Write to cache
        cache_data = [
            {
                "id": str(d.id),
                "entity_type": d.entity_type,
                "key": d.key,
                "label": d.label,
                "field_type": d.field_type,
                "options": d.options,
                "placeholder": d.placeholder,
                "description": d.description,
                "default_value": d.default_value,
                "validation_rules": d.validation_rules,
                "section": d.section,
                "is_active": d.is_active,
                "read_only": d.read_only,
                "visible": d.visible,
                "searchable": d.searchable,
                "filterable": d.filterable,
                "exportable": d.exportable,
                "importable": d.importable
            }
            for d in definitions
        ]
        await MetadataCacheService.set_custom_fields(actor.organization_id, entity_type, cache_data)
        return definitions

    async def create_definition(self, actor: User, data: dict, entity_type: str = "contact") -> CustomFieldDefinition:
        self._ensure_admin(actor)
        
        async with self.db.begin_nested():
            # enforce unique key per org+entity
            existing = await self.db.execute(
                select(CustomFieldDefinition.id).filter(
                    CustomFieldDefinition.organization_id == actor.organization_id,
                    CustomFieldDefinition.entity_type == entity_type,
                    CustomFieldDefinition.key == data["key"],
                    CustomFieldDefinition.is_deleted == False,
                )
            )
            if existing.scalar():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A custom field with key '{data['key']}' already exists"
                )
            definition = CustomFieldDefinition(
                organization_id=actor.organization_id,
                entity_type=entity_type,
                key=data["key"],
                label=data["label"],
                field_type=data.get("field_type", "text"),
                options=data.get("options"),
                placeholder=data.get("placeholder"),
                description=data.get("description"),
                default_value=data.get("default_value"),
                validation_rules=data.get("validation_rules"),
                section=data.get("section"),
                is_active=data.get("is_active", True),
                read_only=data.get("read_only", False),
                visible=data.get("visible", True),
                searchable=data.get("searchable", True),
                filterable=data.get("filterable", True),
                exportable=data.get("exportable", True),
                importable=data.get("importable", True),
                created_by=actor.id,
            )
            self.db.add(definition)
            await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
            await self.db.flush()

        await self.db.refresh(definition)
        await MetadataCacheService.invalidate_custom_fields(actor.organization_id, entity_type)
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CUSTOM_FIELD_CREATED",
            resource_type="CustomFieldDefinition",
            resource_id=str(definition.id),
            action_metadata={"key": definition.key, "label": definition.label}
        )
        return definition

    async def _get_owned(self, actor: User, definition_id: uuid.UUID) -> CustomFieldDefinition:
        res = await self.db.execute(
            select(CustomFieldDefinition).filter(
                CustomFieldDefinition.id == definition_id,
                CustomFieldDefinition.organization_id == actor.organization_id,
                CustomFieldDefinition.is_deleted == False,
            )
        )
        d = res.scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
        return d

    async def update_definition(self, actor: User, definition_id: uuid.UUID, data: dict) -> CustomFieldDefinition:
        self._ensure_admin(actor)
        
        async with self.db.begin_nested():
            d = await self._get_owned(actor, definition_id)
            for key, val in data.items():
                setattr(d, key, val)
            d.updated_by = actor.id
            self.db.add(d)
            await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
            await self.db.flush()

        await self.db.refresh(d)
        await MetadataCacheService.invalidate_custom_fields(actor.organization_id, d.entity_type)
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CUSTOM_FIELD_UPDATED",
            resource_type="CustomFieldDefinition",
            resource_id=str(d.id),
            action_metadata={"key": d.key, "label": d.label}
        )
        return d

    async def delete_definition(self, actor: User, definition_id: uuid.UUID) -> None:
        self._ensure_admin(actor)
        
        async with self.db.begin_nested():
            d = await self._get_owned(actor, definition_id)
            d.is_deleted = True
            d.is_active = False
            self.db.add(d)
            await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
            await self.db.flush()

        await MetadataCacheService.invalidate_custom_fields(actor.organization_id, d.entity_type)
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="CUSTOM_FIELD_DELETED",
            resource_type="CustomFieldDefinition",
            resource_id=str(d.id),
            action_metadata={"key": d.key}
        )


import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.form_definition import FormDefinition
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.custom_field_service import CustomFieldService
from app.services.metadata_cache_service import MetadataCacheService
from app.core.reserved_fields import is_supported_entity_type, SUPPORTED_ENTITY_TYPES


class FormService:
    """Manage tenant Dynamic Form definitions (Phase 7 — Dynamic Forms).

    A form is a LAYOUT over an entity's fields; it never redefines fields or
    stores values. The form layer validates *configuration* (entity ownership,
    known field keys, well-formed sections/overrides); record data continues to
    be validated by MetadataValidationEngine through the existing record APIs.
    Always org-scoped; admin-gated for writes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _ensure_admin(self, actor: User) -> None:
        if actor.role not in ("OrgAdmin", "SuperAdmin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can manage forms.",
            )

    async def _ensure_entity_type_allowed(self, org_id, entity_type: str) -> None:
        if is_supported_entity_type(entity_type):
            return
        from app.models.custom_object import CustomObjectDefinition
        exists = await self.db.execute(
            select(CustomObjectDefinition.id).filter(
                CustomObjectDefinition.organization_id == org_id,
                CustomObjectDefinition.key == entity_type,
                CustomObjectDefinition.is_active == True,
                CustomObjectDefinition.is_deleted == False,
            )
        )
        if not exists.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Forms are not supported for entity '{entity_type}'. "
                       f"Supported: {', '.join(sorted(SUPPORTED_ENTITY_TYPES))} or an active custom object.",
            )

    async def _validate_schema(self, actor: User, entity_type: str, schema: dict | None) -> None:
        """Every field key in the form must be an active field for this entity in
        this org (no unknown/foreign/cross-tenant keys); no duplicate placements;
        sections well-formed (pydantic already checks shape/columns)."""
        schema = schema or {}
        sections = schema.get("sections") or []
        if not isinstance(sections, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="schema.sections must be a list")

        definitions = await CustomFieldService(self.db).list_definitions(actor, entity_type)
        valid_keys = {d.key for d in definitions if d.is_active}

        seen: set[str] = set()
        for section in sections:
            if not isinstance(section, dict):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="each section must be an object")
            for entry in section.get("fields") or []:
                key = entry.get("key") if isinstance(entry, dict) else None
                if not key:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="each field entry needs a 'key'")
                if key not in valid_keys:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown or inactive field '{key}' for entity '{entity_type}'",
                    )
                if key in seen:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Field '{key}' appears more than once in the form",
                    )
                seen.add(key)

    async def list_forms(self, actor: User, entity_type: str, include_inactive: bool = False) -> list[FormDefinition]:
        q = select(FormDefinition).filter(
            FormDefinition.organization_id == actor.organization_id,
            FormDefinition.entity_type == entity_type,
            FormDefinition.is_deleted == False,
        )
        if not include_inactive:
            q = q.filter(FormDefinition.is_active == True)
        q = q.order_by(FormDefinition.created_at.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def _get_owned(self, actor: User, form_id: uuid.UUID) -> FormDefinition:
        res = await self.db.execute(
            select(FormDefinition).filter(
                FormDefinition.id == form_id,
                FormDefinition.organization_id == actor.organization_id,
                FormDefinition.is_deleted == False,
            )
        )
        form = res.scalars().first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
        return form

    async def get_form(self, actor: User, form_id: uuid.UUID) -> FormDefinition:
        return await self._get_owned(actor, form_id)

    async def _clear_other_defaults(self, org_id, entity_type: str, keep_id: uuid.UUID | None) -> None:
        stmt = update(FormDefinition).where(
            FormDefinition.organization_id == org_id,
            FormDefinition.entity_type == entity_type,
            FormDefinition.is_default == True,
            FormDefinition.is_deleted == False,
        )
        if keep_id is not None:
            stmt = stmt.where(FormDefinition.id != keep_id)
        await self.db.execute(stmt.values(is_default=False))

    async def create_form(self, actor: User, entity_type: str, data: dict) -> FormDefinition:
        self._ensure_admin(actor)
        await self._ensure_entity_type_allowed(actor.organization_id, entity_type)
        await self._validate_schema(actor, entity_type, data.get("schema"))

        existing = await self.db.execute(
            select(FormDefinition.id).filter(
                FormDefinition.organization_id == actor.organization_id,
                FormDefinition.entity_type == entity_type,
                FormDefinition.key == data["key"],
                FormDefinition.is_deleted == False,
            )
        )
        if existing.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A form with key '{data['key']}' already exists for {entity_type}",
            )

        form = FormDefinition(
            organization_id=actor.organization_id,
            entity_type=entity_type,
            key=data["key"],
            name=data["name"],
            description=data.get("description"),
            schema=data.get("schema"),
            is_active=data.get("is_active", True),
            is_default=data.get("is_default", False),
            created_by=actor.id,
        )
        self.db.add(form)
        await self.db.flush()
        if form.is_default:
            await self._clear_other_defaults(actor.organization_id, entity_type, form.id)
        await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
        await self.db.flush()
        await self.db.refresh(form)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="FORM_CREATED", resource_type="form_definition",
            resource_id=str(form.id), action_metadata={"entity_type": entity_type, "key": form.key},
        )
        return form

    async def update_form(self, actor: User, form_id: uuid.UUID, data: dict) -> FormDefinition:
        self._ensure_admin(actor)
        form = await self._get_owned(actor, form_id)
        if "schema" in data and data["schema"] is not None:
            await self._validate_schema(actor, form.entity_type, data["schema"])
        for k, v in data.items():
            setattr(form, k, v)
        form.updated_by = actor.id
        self.db.add(form)
        await self.db.flush()
        if form.is_default:
            await self._clear_other_defaults(actor.organization_id, form.entity_type, form.id)
        await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
        await self.db.flush()
        await self.db.refresh(form)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="FORM_UPDATED", resource_type="form_definition",
            resource_id=str(form.id), action_metadata={"entity_type": form.entity_type, "key": form.key},
        )
        return form

    async def delete_form(self, actor: User, form_id: uuid.UUID) -> None:
        self._ensure_admin(actor)
        form = await self._get_owned(actor, form_id)
        form.is_deleted = True
        form.is_active = False
        self.db.add(form)
        await MetadataCacheService.increment_metadata_version(self.db, actor.organization_id)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="FORM_DELETED", resource_type="form_definition",
            resource_id=str(form.id), action_metadata={"entity_type": form.entity_type, "key": form.key},
        )

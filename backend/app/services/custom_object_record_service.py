import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_object import CustomObjectDefinition, CustomObjectRecord
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.custom_field_service import CustomFieldService
from app.services.custom_object_service import CustomObjectService
from app.services.metadata_validation_engine import MetadataValidationEngine, MetadataValidationError
from app.core.record_query import build_filter_expressions, build_order_by, RecordQueryError


class CustomObjectRecordService:
    """CRUD + typed filter/sort/paginate for custom-object records. Reuses the
    Custom Fields Engine for validation and the central record query engine for
    filtering. Always org-scoped."""

    MAX_PAGE_SIZE = 200

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.objects = CustomObjectService(db)

    async def _object(self, actor: User, object_key: str) -> CustomObjectDefinition:
        obj = await self.objects.get_by_key(actor, object_key)
        if not obj.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom object is not active")
        return obj

    async def _definitions(self, actor: User, object_key: str):
        return await CustomFieldService(self.db).list_definitions(actor, object_key)

    async def _sanitize(self, actor: User, obj: CustomObjectDefinition, payload: dict,
                        existing: CustomObjectRecord | None) -> dict:
        definitions = await self._definitions(actor, obj.key)
        if existing is not None:
            def_map = {d.key: d for d in definitions if d.is_active}
            merged = dict(existing.data or {})
            for key, val in (payload or {}).items():
                definition = def_map.get(key)
                required = bool(definition and (definition.validation_rules or {}).get("required") is True)
                if (val is None or val == "") and not required:
                    merged.pop(key, None)
                else:
                    merged[key] = val
            data, exclude_id = merged, existing.id
        else:
            data, exclude_id = (payload or {}), None
        try:
            return await MetadataValidationEngine.validate_and_sanitize(
                self.db, CustomObjectRecord, actor.organization_id, definitions, data,
                exclude_id=exclude_id, json_field="data",
                extra_unique_filters=[CustomObjectRecord.object_definition_id == obj.id],
            )
        except MetadataValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def create_record(self, actor: User, object_key: str, payload: dict) -> CustomObjectRecord:
        obj = await self._object(actor, object_key)
        data = await self._sanitize(actor, obj, payload.get("data") or {}, None)
        rec = CustomObjectRecord(
            organization_id=actor.organization_id,
            object_definition_id=obj.id,
            data=data,
            created_by=actor.id,
        )
        self.db.add(rec)
        await self.db.flush()
        await self.db.refresh(rec)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_RECORD_CREATED", resource_type="custom_object_record",
            resource_id=str(rec.id), action_metadata={"object_key": obj.key},
        )
        return rec

    async def _get_owned(self, actor: User, obj: CustomObjectDefinition, record_id: uuid.UUID) -> CustomObjectRecord:
        res = await self.db.execute(
            select(CustomObjectRecord).filter(
                CustomObjectRecord.id == record_id,
                CustomObjectRecord.organization_id == actor.organization_id,
                CustomObjectRecord.object_definition_id == obj.id,
                CustomObjectRecord.is_deleted == False,
            )
        )
        rec = res.scalars().first()
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return rec

    async def get_record(self, actor: User, object_key: str, record_id: uuid.UUID) -> CustomObjectRecord:
        obj = await self._object(actor, object_key)
        return await self._get_owned(actor, obj, record_id)

    async def update_record(self, actor: User, object_key: str, record_id: uuid.UUID, payload: dict) -> CustomObjectRecord:
        obj = await self._object(actor, object_key)
        rec = await self._get_owned(actor, obj, record_id)
        rec.data = await self._sanitize(actor, obj, payload.get("data") or {}, rec)
        rec.updated_by = actor.id
        self.db.add(rec)
        await self.db.flush()
        await self.db.refresh(rec)
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_RECORD_UPDATED", resource_type="custom_object_record",
            resource_id=str(rec.id), action_metadata={"object_key": obj.key},
        )
        return rec

    async def delete_record(self, actor: User, object_key: str, record_id: uuid.UUID) -> None:
        obj = await self._object(actor, object_key)
        rec = await self._get_owned(actor, obj, record_id)
        rec.is_deleted = True
        self.db.add(rec)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="CUSTOM_OBJECT_RECORD_DELETED", resource_type="custom_object_record",
            resource_id=str(rec.id), action_metadata={"object_key": obj.key},
        )

    async def list_records(self, actor: User, object_key: str, *, filters: list | None = None,
                           sort: str | None = None, page: int = 1, page_size: int = 50) -> dict:
        obj = await self._object(actor, object_key)
        page = max(1, page)
        page_size = max(1, min(page_size, self.MAX_PAGE_SIZE))

        definitions = await self._definitions(actor, obj.key)
        # Only active + filterable fields are queryable/sortable (guardrail).
        filterable = {d.key: d for d in definitions if d.is_active and d.filterable}

        base = [
            CustomObjectRecord.organization_id == actor.organization_id,
            CustomObjectRecord.object_definition_id == obj.id,
            CustomObjectRecord.is_deleted == False,
        ]
        try:
            base += build_filter_expressions(CustomObjectRecord, filterable, filters or [])
            order_by = build_order_by(CustomObjectRecord, filterable, sort)
        except RecordQueryError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        total = (await self.db.execute(
            select(func.count(CustomObjectRecord.id)).filter(*base)
        )).scalar() or 0

        q = select(CustomObjectRecord).filter(*base)
        q = q.order_by(order_by if order_by is not None else CustomObjectRecord.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        items = list((await self.db.execute(q)).scalars().all())
        return {"items": items, "total": total, "page": page, "page_size": page_size}

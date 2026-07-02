import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_field_definition import CustomFieldDefinition
from app.models.user import User


class CustomFieldService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_definitions(self, actor: User, entity_type: str = "contact") -> list[CustomFieldDefinition]:
        res = await self.db.execute(
            select(CustomFieldDefinition).filter(
                CustomFieldDefinition.organization_id == actor.organization_id,
                CustomFieldDefinition.entity_type == entity_type,
                CustomFieldDefinition.is_deleted == False,
            ).order_by(CustomFieldDefinition.created_at.asc())
        )
        return list(res.scalars().all())

    async def create_definition(self, actor: User, data: dict, entity_type: str = "contact") -> CustomFieldDefinition:
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A custom field with key '{data['key']}' already exists")
        definition = CustomFieldDefinition(
            organization_id=actor.organization_id,
            entity_type=entity_type,
            key=data["key"],
            label=data["label"],
            field_type=data.get("field_type", "text"),
            options=data.get("options"),
            created_by=actor.id,
        )
        self.db.add(definition)
        await self.db.flush()
        await self.db.refresh(definition)
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
        d = await self._get_owned(actor, definition_id)
        for key, val in data.items():
            setattr(d, key, val)
        self.db.add(d)
        await self.db.flush()
        await self.db.refresh(d)
        return d

    async def delete_definition(self, actor: User, definition_id: uuid.UUID) -> None:
        d = await self._get_owned(actor, definition_id)
        d.is_deleted = True
        self.db.add(d)
        await self.db.flush()

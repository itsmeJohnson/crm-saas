from typing import Generic, Type, TypeVar, Any, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=Any)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: Any) -> ModelType | None:
        query = select(self.model).filter(self.model.id == id)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted == False)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        query = select(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted == False)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: Any) -> ModelType:
        if isinstance(obj_in, dict):
            create_data = obj_in
        else:
            create_data = obj_in.model_dump()
        
        db_obj = self.model(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: Any) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def remove(self, id: Any) -> ModelType | None:
        obj = await self.get(id)
        if obj:
            if hasattr(obj, "is_deleted"):
                obj.is_deleted = True
                self.db.add(obj)
            else:
                await self.db.delete(obj)
            await self.db.flush()
        return obj


import uuid

class TenantRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession, organization_id: uuid.UUID):
        self.model = model
        self.db = db
        
        # Enforce model eligibility (fail closed at construction)
        if not hasattr(model, "organization_id"):
            raise TypeError(f"Model {model.__name__} does not have an 'organization_id' attribute and cannot be used with TenantRepository.")
            
        if organization_id is None:
            raise ValueError("TenantRepository operations require a non-None organization_id context (fail closed).")
        self.organization_id = organization_id

    async def get(self, id: Any) -> ModelType | None:
        query = select(self.model).filter(
            self.model.id == id,
            self.model.organization_id == self.organization_id
        )
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted == False)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        query = select(self.model).filter(self.model.organization_id == self.organization_id)
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted == False)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: Any) -> ModelType:
        if isinstance(obj_in, dict):
            create_data = obj_in.copy()
        else:
            create_data = obj_in.model_dump()
            
        # Reject override attempts to other tenants
        if "organization_id" in create_data and create_data["organization_id"] != self.organization_id:
            raise ValueError("Override of organization_id is not allowed (fail closed).")

        create_data["organization_id"] = self.organization_id
        db_obj = self.model(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: Any) -> ModelType:
        # Ensure the object currently belongs to this tenant before update
        if getattr(db_obj, "organization_id", None) != self.organization_id:
            raise ValueError("Cross-tenant database modification blocked (fail closed).")
            
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        # Immutability check: forbid changing organization_id
        if "organization_id" in update_data and update_data["organization_id"] != self.organization_id:
            raise ValueError("Mutation of organization_id is not allowed (fail closed).")

        for field, value in update_data.items():
            if field == "organization_id":
                continue
            setattr(db_obj, field, value)
        
        # Double check after setting attributes
        if getattr(db_obj, "organization_id", None) != self.organization_id:
            raise ValueError("Cross-tenant database modification blocked (fail closed).")

        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def remove(self, id: Any) -> ModelType | None:
        obj = await self.get(id) # get() automatically scopes to self.organization_id
        if obj:
            if hasattr(obj, "is_deleted"):
                obj.is_deleted = True
                self.db.add(obj)
            else:
                await self.db.delete(obj)
            await self.db.flush()
        return obj

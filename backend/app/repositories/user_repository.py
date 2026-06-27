import uuid
from datetime import datetime, timezone
from typing import Any, Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def create_user(self, organization_id: uuid.UUID, user_data: dict) -> User:
        user_data["organization_id"] = organization_id
        return await self.create(user_data)

    async def get_user_by_id(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        query = select(self.model).filter(
            self.model.id == user_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_user_by_email(self, organization_id: uuid.UUID, email: str) -> User | None:
        query = select(self.model).filter(
            self.model.email == email,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_email_global(self, email: str) -> User | None:
        query = select(self.model).filter(
            self.model.email == email,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_users(self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100) -> Sequence[User]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        ).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search_users(self, organization_id: uuid.UUID, query_str: str, skip: int = 0, limit: int = 100) -> Sequence[User]:
        search_filter = f"%{query_str}%"
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False,
            or_(
                self.model.email.ilike(search_filter),
                self.model.first_name.ilike(search_filter),
                self.model.last_name.ilike(search_filter)
            )
        ).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def paginate_users(
        self, 
        organization_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        reporting_to_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[User], int]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        if reporting_to_id is not None:
            # Include the manager/TL themselves alongside their direct reports,
            # so callers can resolve "assigned to me" without a separate lookup.
            query = query.filter(
                or_(
                    self.model.reporting_to_id == reporting_to_id,
                    self.model.id == reporting_to_id
                )
            )
        if role:
            query = query.filter(self.model.role == role)
        if is_active is not None:
            query = query.filter(self.model.is_active == is_active)
        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.email.ilike(search_filter),
                    self.model.first_name.ilike(search_filter),
                    self.model.last_name.ilike(search_filter)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get records
        records_query = query.offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def update_user(self, organization_id: uuid.UUID, user_id: uuid.UUID, user_data: dict) -> User | None:
        user = await self.get_user_by_id(organization_id, user_id)
        if not user:
            return None
        return await self.update(user, user_data)

    async def toggle_active(self, organization_id: uuid.UUID, user_id: uuid.UUID, is_active: bool) -> User | None:
        user = await self.get_user_by_id(organization_id, user_id)
        if not user:
            return None
        user.is_active = is_active
        self.db.add(user)
        
        # If deactivating, unassign their leads
        if not is_active:
            from app.models.lead import Lead
            from sqlalchemy import update
            await self.db.execute(
                update(Lead)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.assigned_user_id == user_id
                )
                .values(assigned_user_id=None)
            )
            
        await self.db.flush()
        return user

    async def soft_delete_user(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = await self.get_user_by_id(organization_id, user_id)
        if not user:
            return None
        user.is_deleted = True
        user.deleted_at = datetime.now(timezone.utc)
        self.db.add(user)
        
        # Unassign their leads
        from app.models.lead import Lead
        from sqlalchemy import update
        await self.db.execute(
            update(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.assigned_user_id == user_id
            )
            .values(assigned_user_id=None)
        )
        
        await self.db.flush()
        return user

    async def count_org_admins(self, organization_id: uuid.UUID) -> int:
        query = select(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id,
            self.model.role == "OrgAdmin",
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

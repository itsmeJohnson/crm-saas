import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.activity import Activity
from app.repositories.base import BaseRepository

class ActivityRepository(BaseRepository[Activity]):
    def __init__(self, db: AsyncSession):
        super().__init__(Activity, db)

    async def create_activity(self, organization_id: uuid.UUID, activity_data: dict, created_by: uuid.UUID) -> Activity:
        activity_data["organization_id"] = organization_id
        activity_data["created_by"] = created_by
        return await self.create(activity_data)

    async def get_activity_by_id(self, organization_id: uuid.UUID, activity_id: uuid.UUID) -> Activity | None:
        query = select(self.model).filter(
            self.model.id == activity_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def paginate_activities(
        self, 
        organization_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        activity_type: str | None = None,
        status: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[Activity], int]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )

        if activity_type:
            query = query.filter(self.model.activity_type == activity_type)

        if status:
            query = query.filter(self.model.status == status)

        if assigned_user_id:
            query = query.filter(self.model.assigned_user_id == assigned_user_id)

        if lead_id:
            query = query.filter(self.model.lead_id == lead_id)
        
        if contact_id:
            query = query.filter(self.model.contact_id == contact_id)

        if company_id:
            query = query.filter(self.model.company_id == company_id)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get records ordered by due_date or created_at desc if due_date is null
        records_query = query.order_by(self.model.due_date.asc().nulls_last(), self.model.created_at.desc()).offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def update_activity(self, organization_id: uuid.UUID, activity_id: uuid.UUID, activity_data: dict) -> Activity | None:
        activity = await self.get_activity_by_id(organization_id, activity_id)
        if not activity:
            return None
        return await self.update(activity, activity_data)

    async def soft_delete_activity(self, organization_id: uuid.UUID, activity_id: uuid.UUID) -> Activity | None:
        activity = await self.get_activity_by_id(organization_id, activity_id)
        if not activity:
            return None
        activity.is_deleted = True
        activity.deleted_at = datetime.now(timezone.utc)
        self.db.add(activity)
        await self.db.flush()
        return activity

    async def soft_delete_by_parent(self, organization_id: uuid.UUID, parent_type: str, parent_id: uuid.UUID) -> int:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        if parent_type == "lead":
            query = query.filter(self.model.lead_id == parent_id)
        elif parent_type == "contact":
            query = query.filter(self.model.contact_id == parent_id)
        elif parent_type == "company":
            query = query.filter(self.model.company_id == parent_id)
        else:
            return 0

        result = await self.db.execute(query)
        activities = result.scalars().all()
        
        count = 0
        now = datetime.now(timezone.utc)
        for act in activities:
            act.is_deleted = True
            act.deleted_at = now
            self.db.add(act)
            count += 1
            
        await self.db.flush()
        return count

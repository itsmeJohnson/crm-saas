import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.contact import Contact
from app.repositories.base import BaseRepository

class ContactRepository(BaseRepository[Contact]):
    def __init__(self, db: AsyncSession):
        super().__init__(Contact, db)

    async def create_contact(self, organization_id: uuid.UUID, contact_data: dict, created_by: uuid.UUID) -> Contact:
        contact_data["organization_id"] = organization_id
        contact_data["created_by"] = created_by
        return await self.create(contact_data)

    async def get_contact_by_id(self, organization_id: uuid.UUID, contact_id: uuid.UUID) -> Contact | None:
        query = select(self.model).filter(
            self.model.id == contact_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def paginate_contacts(
        self, 
        organization_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        company_id: uuid.UUID | None = None
    ) -> Tuple[Sequence[Contact], int]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )

        if company_id:
            query = query.filter(self.model.company_id == company_id)
        
        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(search_filter),
                    self.model.last_name.ilike(search_filter),
                    self.model.email.ilike(search_filter),
                    self.model.phone.ilike(search_filter),
                    self.model.job_title.ilike(search_filter)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get records ordered by last_name, first_name
        records_query = query.order_by(self.model.last_name.asc(), self.model.first_name.asc()).offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def update_contact(self, organization_id: uuid.UUID, contact_id: uuid.UUID, contact_data: dict) -> Contact | None:
        contact = await self.get_contact_by_id(organization_id, contact_id)
        if not contact:
            return None
        return await self.update(contact, contact_data)

    async def soft_delete_contact(self, organization_id: uuid.UUID, contact_id: uuid.UUID) -> Contact | None:
        contact = await self.get_contact_by_id(organization_id, contact_id)
        if not contact:
            return None
        contact.is_deleted = True
        contact.deleted_at = datetime.now(timezone.utc)
        self.db.add(contact)
        await self.db.flush()
        return contact

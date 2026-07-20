import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_, String
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

    def _apply_filters(
        self,
        query,
        organization_id: uuid.UUID,
        search_query: str | None = None,
        company_id: uuid.UUID | None = None,
        assigned_user_id: uuid.UUID | None = None,
        tag: str | None = None,
        has_email: bool | None = None,
        created_from=None,
        created_to=None,
    ):
        query = query.filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False,
        )
        if company_id:
            query = query.filter(self.model.company_id == company_id)
        if assigned_user_id:
            query = query.filter(self.model.assigned_user_id == assigned_user_id)
        if has_email is True:
            query = query.filter(self.model.email.isnot(None), self.model.email != "")
        elif has_email is False:
            query = query.filter(or_(self.model.email.is_(None), self.model.email == ""))
        if created_from is not None:
            query = query.filter(self.model.created_at >= created_from)
        if created_to is not None:
            query = query.filter(self.model.created_at <= created_to)
        if tag:
            # JSON array contains: portable LIKE match on the serialized tag
            query = query.filter(func.lower(func.cast(self.model.tags, String)).like(f'%"{tag.lower()}"%'))
        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(search_filter),
                    self.model.last_name.ilike(search_filter),
                    self.model.email.ilike(search_filter),
                    self.model.phone.ilike(search_filter),
                    self.model.job_title.ilike(search_filter),
                )
            )
        return query

    async def paginate_contacts(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        search_query: str | None = None,
        company_id: uuid.UUID | None = None,
        assigned_user_id: uuid.UUID | None = None,
        tag: str | None = None,
        has_email: bool | None = None,
        created_from=None,
        created_to=None,
    ) -> Tuple[Sequence[Contact], int]:
        query = self._apply_filters(
            select(self.model), organization_id, search_query, company_id,
            assigned_user_id, tag, has_email, created_from, created_to,
        )

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        records_query = query.order_by(self.model.last_name.asc(), self.model.first_name.asc()).offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def stream_for_export(self, organization_id: uuid.UUID, max_rows: int = 50000, **filters) -> Sequence[Contact]:
        query = self._apply_filters(select(self.model), organization_id, **filters)
        query = query.order_by(self.model.last_name.asc(), self.model.first_name.asc()).limit(max_rows)
        res = await self.db.execute(query)
        return res.scalars().all()

    async def find_duplicates(
        self, organization_id: uuid.UUID, email: str | None = None, phone: str | None = None,
        exclude_contact_id: uuid.UUID | None = None,
    ) -> Sequence[Contact]:
        if not email and not phone:
            return []
        clauses = []
        if email:
            clauses.append(func.lower(self.model.email) == email.lower())
        if phone:
            clauses.append(self.model.phone == phone)
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False,
            or_(*clauses),
        )
        if exclude_contact_id:
            query = query.filter(self.model.id != exclude_contact_id)
        res = await self.db.execute(query)
        return res.scalars().all()

    async def get_contacts_for_update(self, organization_id: uuid.UUID, contact_ids: list[uuid.UUID]) -> Sequence[Contact]:
        query = select(self.model).filter(
            self.model.id.in_(contact_ids),
            self.model.organization_id == organization_id,
            self.model.is_deleted == False,
        ).with_for_update().order_by(self.model.id)
        res = await self.db.execute(query)
        return res.scalars().all()

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

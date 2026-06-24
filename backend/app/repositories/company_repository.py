import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.company import Company
from app.repositories.base import BaseRepository

class CompanyRepository(BaseRepository[Company]):
    def __init__(self, db: AsyncSession):
        super().__init__(Company, db)

    async def create_company(self, organization_id: uuid.UUID, company_data: dict, created_by: uuid.UUID) -> Company:
        company_data["organization_id"] = organization_id
        company_data["created_by"] = created_by
        return await self.create(company_data)

    async def get_company_by_id(self, organization_id: uuid.UUID, company_id: uuid.UUID) -> Company | None:
        query = select(self.model).filter(
            self.model.id == company_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def paginate_companies(
        self, 
        organization_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None
    ) -> Tuple[Sequence[Company], int]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        
        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.name.ilike(search_filter),
                    self.model.domain.ilike(search_filter),
                    self.model.industry.ilike(search_filter)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get records ordered by created_at desc
        records_query = query.order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def update_company(self, organization_id: uuid.UUID, company_id: uuid.UUID, company_data: dict) -> Company | None:
        company = await self.get_company_by_id(organization_id, company_id)
        if not company:
            return None
        return await self.update(company, company_data)

    async def soft_delete_company(self, organization_id: uuid.UUID, company_id: uuid.UUID) -> Company | None:
        company = await self.get_company_by_id(organization_id, company_id)
        if not company:
            return None
        company.is_deleted = True
        company.deleted_at = datetime.now(timezone.utc)
        self.db.add(company)
        await self.db.flush()
        return company

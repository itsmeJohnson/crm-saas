import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.lead import Lead
from app.repositories.base import BaseRepository

class LeadRepository(BaseRepository[Lead]):
    def __init__(self, db: AsyncSession):
        super().__init__(Lead, db)

    async def create_lead(self, organization_id: uuid.UUID, lead_data: dict, created_by: uuid.UUID) -> Lead:
        lead_data["organization_id"] = organization_id
        lead_data["created_by"] = created_by

        if "stage_id" not in lead_data or not lead_data["stage_id"]:
            from app.models.pipeline import PipelineStage
            stage_query = select(PipelineStage.id).filter(
                PipelineStage.organization_id == organization_id,
                PipelineStage.is_system_default == True,
                PipelineStage.is_deleted == False
            ).limit(1)
            res = await self.db.execute(stage_query)
            stage_id = res.scalar()

            if not stage_id:
                stage_query_fallback = select(PipelineStage.id).filter(
                    PipelineStage.organization_id == organization_id,
                    PipelineStage.is_deleted == False
                ).order_by(PipelineStage.order_position).limit(1)
                res_fallback = await self.db.execute(stage_query_fallback)
                stage_id = res_fallback.scalar()

            lead_data["stage_id"] = stage_id

        return await self.create(lead_data)

    async def get_lead_by_id(self, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
        query = select(self.model).filter(
            self.model.id == lead_id,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_lead_by_email(self, organization_id: uuid.UUID, email: str) -> Lead | None:
        query = select(self.model).filter(
            self.model.email == email,
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def paginate_leads(
        self, 
        organization_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        search_query: str | None = None,
        status: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        name: str | None = None,
        city: str | None = None
    ) -> Tuple[Sequence[Lead], int]:
        query = select(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.is_deleted == False
        )

        if status:
            query = query.filter(self.model.status == status)

        if assigned_user_id:
            query = query.filter(self.model.assigned_user_id == assigned_user_id)
        
        if name:
            name_filter = f"%{name}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(name_filter),
                    self.model.last_name.ilike(name_filter)
                )
            )

        if city:
            city_filter = f"%{city}%"
            query = query.filter(self.model.city.ilike(city_filter))

        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(search_filter),
                    self.model.last_name.ilike(search_filter),
                    self.model.email.ilike(search_filter),
                    self.model.phone.ilike(search_filter),
                    self.model.company_name.ilike(search_filter),
                    self.model.title.ilike(search_filter),
                    self.model.source.ilike(search_filter),
                    self.model.city.ilike(search_filter)
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

    async def update_lead(self, organization_id: uuid.UUID, lead_id: uuid.UUID, lead_data: dict) -> Lead | None:
        lead = await self.get_lead_by_id(organization_id, lead_id)
        if not lead:
            return None
        return await self.update(lead, lead_data)

    async def soft_delete_lead(self, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
        lead = await self.get_lead_by_id(organization_id, lead_id)
        if not lead:
            return None
        lead.is_deleted = True
        lead.deleted_at = datetime.now(timezone.utc)
        self.db.add(lead)
        await self.db.flush()
        return lead

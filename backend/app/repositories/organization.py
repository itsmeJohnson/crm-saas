from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, db: AsyncSession):
        super().__init__(Organization, db)

    async def get_by_slug(self, slug: str) -> Organization | None:
        query = select(self.model).filter(
            self.model.slug == slug,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def create(self, obj_in: any) -> Organization:
        org = await super().create(obj_in)
        from app.models.pipeline import Pipeline, PipelineStage
        
        # Create default pipeline
        pipeline = Pipeline(
            organization_id=org.id,
            name="Default Pipeline",
            description="Primary Sales Pipeline",
            is_default=True,
            is_active=True
        )
        self.db.add(pipeline)
        await self.db.flush()

        stages = [
            ("Fresh Leads", 1, True),
            ("Contacted", 2, False),
            ("Followup", 3, False),
            ("Dropped", 4, False),
            ("Converted", 5, False)
        ]
        for name, pos, is_default in stages:
            stage = PipelineStage(
                organization_id=org.id,
                pipeline_id=pipeline.id,
                name=name,
                order_position=pos,
                is_system_default=is_default
            )
            self.db.add(stage)
        await self.db.flush()
        return org

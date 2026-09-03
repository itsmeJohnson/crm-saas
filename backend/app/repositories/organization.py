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
        # Template-aware default pipeline. With no PIPELINE_TEMPLATE env var this is
        # the original generic pipeline; a single-tenant instance (e.g. LoanNest with
        # PIPELINE_TEMPLATE=real_estate) auto-provisions its vertical pipeline instead.
        from app.core.pipeline_templates import default_pipeline_meta, default_stages

        pipeline_name, pipeline_desc = default_pipeline_meta()
        pipeline = Pipeline(
            organization_id=org.id,
            name=pipeline_name,
            description=pipeline_desc,
            is_default=True,
            is_active=True
        )
        self.db.add(pipeline)
        await self.db.flush()

        stages = default_stages()
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

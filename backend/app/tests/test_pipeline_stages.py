import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.repositories.organization import OrganizationRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import PipelineStage
from app.models.lead import Lead

@pytest.mark.asyncio
async def test_pipeline_stages_seeding_and_constraints(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    
    # 1. Test automatic seeding on organization creation
    org = await org_repo.create({"name": "Pipeline Org", "slug": "pipeline-org"})
    await db.commit()
    org_id = org.id
    
    # Fetch stages
    stages_query = select(PipelineStage).filter(
        PipelineStage.organization_id == org_id,
        PipelineStage.is_deleted == False
    ).order_by(PipelineStage.order_position)
    res = await db.execute(stages_query)
    stages = res.scalars().all()
    
    assert len(stages) == 5
    assert stages[0].name == "Fresh Leads"
    assert stages[0].order_position == 1
    assert stages[0].is_system_default is True
    assert stages[1].name == "Contacted"
    assert stages[2].name == "Followup"
    assert stages[3].name == "Dropped"
    assert stages[4].name == "Converted"

    # 2. Test unique constraints
    from app.models.pipeline import Pipeline
    pipeline_stmt = select(Pipeline).filter(Pipeline.organization_id == org_id, Pipeline.is_default == True)
    pipeline = (await db.execute(pipeline_stmt)).scalars().first()
    pipeline_id = pipeline.id

    # Duplicate name within same pipeline
    dup_name_stage = PipelineStage(
        organization_id=org_id,
        pipeline_id=pipeline_id,
        name="Fresh Leads",
        order_position=10,
        is_system_default=False
    )
    db.add(dup_name_stage)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    # Duplicate order position within same pipeline
    dup_pos_stage = PipelineStage(
        organization_id=org_id,
        pipeline_id=pipeline_id,
        name="New Stage",
        order_position=1,
        is_system_default=False
    )
    db.add(dup_pos_stage)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

@pytest.mark.asyncio
async def test_lead_stage_default_assignment(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    
    org = await org_repo.create({"name": "Lead Stage Org", "slug": "lead-stage-org"})
    lead_repo = LeadRepository(db, org.id)
    user = await user_repo.create_user(org.id, {
        "email": "agent_pipeline@org.com",
        "hashed_password": "hash",
        "role": "Employee",
        "is_active": True
    })
    await db.commit()
    
    # Create lead without stage_id
    lead = await lead_repo.create_lead({
        "first_name": "John",
        "last_name": "Doe",
        "title": "Software Lead"
    }, user.id)
    await db.commit()
    
    # Refresh and verify stage
    await db.refresh(lead)
    assert lead.stage_id is not None
    
    # Fetch stage details
    stage = await db.get(PipelineStage, lead.stage_id)
    assert stage.name == "Fresh Leads"
    assert stage.is_system_default is True

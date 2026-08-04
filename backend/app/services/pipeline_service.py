import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.pipeline import Pipeline, PipelineStage
from app.models.lead import Lead
from app.models.user import User
from app.core.exceptions import PipelineStageValidationError, PipelineStageDeletionError
from app.schemas.pipeline import PipelineStageCreate, PipelineStageUpdate
from app.services.metadata_cache_service import MetadataCacheService
from app.services.audit_service import AuditService


def _ensure_admin(actor: User) -> None:
    """Enforces administrator role check."""
    if actor.role not in ("OrgAdmin", "SuperAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action."
        )


async def _get_or_create_default_pipeline(db: AsyncSession, org_id: uuid.UUID) -> Pipeline:
    """Fetches the default pipeline for an organization, creating it if missing."""
    query = select(Pipeline).filter(
        Pipeline.organization_id == org_id,
        Pipeline.is_default == True,
        Pipeline.is_deleted == False
    )
    res = await db.execute(query)
    pipeline = res.scalar()
    if not pipeline:
        pipeline = Pipeline(
            organization_id=org_id,
            name="Default Pipeline",
            description="Primary Sales Pipeline",
            is_default=True,
            is_active=True
        )
        db.add(pipeline)
        await db.flush()
    return pipeline


def _stage_to_cache(s: PipelineStage) -> dict:
    return {
        "id": str(s.id),
        "organization_id": str(s.organization_id),
        "pipeline_id": str(s.pipeline_id),
        "name": s.name,
        "order_position": s.order_position,
        "is_system_default": s.is_system_default,
        "color": s.color,
        "probability": s.probability,
        "is_won": s.is_won,
        "is_lost": s.is_lost,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _pipeline_to_cache(p: Pipeline) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "is_default": p.is_default,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "stages": [_stage_to_cache(s) for s in sorted(p.stages, key=lambda x: x.order_position)],
    }


def _pipeline_from_cache(p: dict, org_id: uuid.UUID) -> Pipeline:
    pipeline = Pipeline(
        id=uuid.UUID(p["id"]),
        organization_id=org_id,
        name=p["name"],
        description=p.get("description"),
        is_default=p.get("is_default", False),
        is_active=p.get("is_active", True),
        created_at=datetime.fromisoformat(p["created_at"]) if p.get("created_at") else None,
        updated_at=datetime.fromisoformat(p["updated_at"]) if p.get("updated_at") else None,
    )
    # Set the (selectin) relationship explicitly on this transient object so
    # serialization reads the cached stages without touching the DB.
    pipeline.stages = [
        PipelineStage(
            id=uuid.UUID(s["id"]),
            organization_id=uuid.UUID(s["organization_id"]),
            pipeline_id=uuid.UUID(s["pipeline_id"]),
            name=s["name"],
            order_position=s["order_position"],
            is_system_default=s["is_system_default"],
            color=s.get("color", "#4F46E5"),
            probability=s.get("probability", 0),
            is_won=s.get("is_won", False),
            is_lost=s.get("is_lost", False),
            is_active=s.get("is_active", True),
            created_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None,
            updated_at=datetime.fromisoformat(s["updated_at"]) if s.get("updated_at") else None,
        )
        for s in p.get("stages", [])
    ]
    return pipeline


# Pipeline operations
async def list_pipelines(db: AsyncSession, actor: User) -> list[Pipeline]:
    # Cache lookup first. Only trust cache entries that carry the full shape
    # (timestamps + nested stages) so older/partial cache payloads auto-heal by
    # falling through to a fresh DB read below.
    cached = await MetadataCacheService.get_pipelines(actor.organization_id)
    if cached is not None and all(
        isinstance(p, dict) and "created_at" in p and "stages" in p for p in cached
    ):
        return [_pipeline_from_cache(p, actor.organization_id) for p in cached]

    # stages is lazy="selectin", so this query eager-loads them automatically.
    res = await db.execute(
        select(Pipeline).filter(
            Pipeline.organization_id == actor.organization_id,
            Pipeline.is_deleted == False
        ).order_by(Pipeline.created_at.asc())
    )
    pipelines = list(res.scalars().all())

    await MetadataCacheService.set_pipelines(
        actor.organization_id, [_pipeline_to_cache(p) for p in pipelines]
    )
    return pipelines


async def get_pipeline(db: AsyncSession, actor: User, pipeline_id: uuid.UUID) -> Pipeline:
    res = await db.execute(
        select(Pipeline).filter(
            Pipeline.organization_id == actor.organization_id,
            Pipeline.id == pipeline_id,
            Pipeline.is_deleted == False
        )
    )
    pipeline = res.scalar()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


async def create_pipeline(db: AsyncSession, actor: User, data: dict) -> Pipeline:
    _ensure_admin(actor)
    org_id = actor.organization_id

    async with db.begin_nested():
        # Check duplicate name
        existing = await db.execute(
            select(Pipeline.id).filter(
                Pipeline.organization_id == org_id,
                Pipeline.name == data["name"],
                Pipeline.is_deleted == False
            )
        )
        if existing.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline '{data['name']}' already exists"
            )

        if data.get("is_default"):
            await db.execute(
                update(Pipeline)
                .filter(Pipeline.organization_id == org_id, Pipeline.is_deleted == False)
                .values(is_default=False)
            )

        pipeline = Pipeline(
            organization_id=org_id,
            name=data["name"],
            description=data.get("description"),
            is_default=data.get("is_default", False),
            is_active=True
        )
        db.add(pipeline)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await db.refresh(pipeline)
    await MetadataCacheService.invalidate_pipelines(org_id)
    await AuditService(db).log_event(
        organization_id=org_id,
        actor_user_id=actor.id,
        action="PIPELINE_CREATED",
        resource_type="Pipeline",
        resource_id=str(pipeline.id),
        action_metadata={"name": pipeline.name}
    )
    return pipeline


async def update_pipeline(db: AsyncSession, actor: User, pipeline_id: uuid.UUID, data: dict) -> Pipeline:
    _ensure_admin(actor)
    org_id = actor.organization_id

    async with db.begin_nested():
        pipeline = await get_pipeline(db, actor, pipeline_id)
        
        name = data.get("name")
        if name is not None:
            # Check duplicate name
            existing = await db.execute(
                select(Pipeline.id).filter(
                    Pipeline.organization_id == org_id,
                    Pipeline.name == name,
                    Pipeline.id != pipeline_id,
                    Pipeline.is_deleted == False
                )
            )
            if existing.scalar():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pipeline '{name}' already exists"
                )
            pipeline.name = name

        if "description" in data:
            pipeline.description = data["description"]

        if "is_active" in data:
            pipeline.is_active = bool(data["is_active"])

        if data.get("is_default"):
            await db.execute(
                update(Pipeline)
                .filter(Pipeline.organization_id == org_id, Pipeline.is_deleted == False)
                .values(is_default=False)
            )
            pipeline.is_default = True

        db.add(pipeline)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await db.refresh(pipeline)
    await MetadataCacheService.invalidate_pipelines(org_id)
    await AuditService(db).log_event(
        organization_id=org_id,
        actor_user_id=actor.id,
        action="PIPELINE_UPDATED",
        resource_type="Pipeline",
        resource_id=str(pipeline.id),
        action_metadata={"name": pipeline.name}
    )
    return pipeline


async def delete_pipeline(
    db: AsyncSession,
    actor: User,
    pipeline_id: uuid.UUID,
    reassignment_pipeline_id: uuid.UUID | None = None
) -> None:
    _ensure_admin(actor)
    org_id = actor.organization_id

    async with db.begin_nested():
        pipeline = await get_pipeline(db, actor, pipeline_id)
        if pipeline.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the default pipeline. Mark another pipeline as default first."
            )

        # Check active leads referencing this pipeline
        lead_count_query = select(func.count(Lead.id)).filter(
            Lead.organization_id == org_id,
            Lead.pipeline_id == pipeline_id,
            Lead.is_deleted == False
        )
        lead_count_res = await db.execute(lead_count_query)
        lead_count = lead_count_res.scalar() or 0

        if lead_count > 0:
            if not reassignment_pipeline_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete pipeline because it contains {lead_count} active lead(s). Please provide a reassignment pipeline."
                )
            if reassignment_pipeline_id == pipeline_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reassignment pipeline cannot be the same as the pipeline being deleted"
                )

            # Validate reassignment pipeline
            reassign_query = select(Pipeline).filter(
                Pipeline.organization_id == org_id,
                Pipeline.id == reassignment_pipeline_id,
                Pipeline.is_deleted == False
            )
            reassign_res = await db.execute(reassign_query)
            reassign_pipeline = reassign_res.scalar()
            if not reassign_pipeline:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reassignment pipeline not found"
                )

            # Get default stage of reassignment pipeline
            stage_query = select(PipelineStage).filter(
                PipelineStage.pipeline_id == reassignment_pipeline_id,
                PipelineStage.is_deleted == False
            ).order_by(PipelineStage.order_position.asc())
            stage_res = await db.execute(stage_query)
            reassign_stage = stage_res.scalars().first()
            if not reassign_stage:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reassignment pipeline has no stages to map leads to"
                )

            # Move leads to reassignment pipeline and its first stage
            await db.execute(
                update(Lead)
                .filter(Lead.organization_id == org_id, Lead.pipeline_id == pipeline_id, Lead.is_deleted == False)
                .values(pipeline_id=reassignment_pipeline_id, stage_id=reassign_stage.id)
            )

        # Soft delete pipeline
        pipeline.is_deleted = True
        pipeline.is_active = False
        pipeline.deleted_at = datetime.now(timezone.utc)
        pipeline.name = f"{pipeline.name} (deleted {uuid.uuid4().hex[:8]})"
        db.add(pipeline)

        # Soft delete pipeline stages as well
        stages_query = select(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.is_deleted == False
        )
        stages_res = await db.execute(stages_query)
        stages = stages_res.scalars().all()
        for stage in stages:
            stage.is_deleted = True
            stage.is_active = False
            stage.deleted_at = datetime.now(timezone.utc)
            stage.name = f"{stage.name} (deleted {uuid.uuid4().hex[:8]})"
            db.add(stage)

        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await MetadataCacheService.invalidate_pipelines(org_id)
    await AuditService(db).log_event(
        organization_id=org_id,
        actor_user_id=actor.id,
        action="PIPELINE_DELETED",
        resource_type="Pipeline",
        resource_id=str(pipeline_id),
        action_metadata={"id": str(pipeline_id)}
    )


# Stage operations
async def create_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    data: dict | PipelineStageCreate,
    actor: User | None = None
) -> PipelineStage:
    if actor:
        _ensure_admin(actor)

    if hasattr(data, "model_dump"):
        data_dict = data.model_dump()
    else:
        data_dict = dict(data)

    name = data_dict.get("name")
    order_position = data_dict.get("order_position")
    is_system_default = data_dict.get("is_system_default", False)
    pipeline_id = data_dict.get("pipeline_id")

    if not name or not name.strip():
        raise PipelineStageValidationError("Stage name cannot be empty")
    name = name.strip()

    # Determine or auto-provision pipeline_id
    if not pipeline_id:
        default_pipeline = await _get_or_create_default_pipeline(db, org_id)
        pipeline_id = default_pipeline.id
    else:
        pipeline_id = uuid.UUID(str(pipeline_id)) if not isinstance(pipeline_id, uuid.UUID) else pipeline_id

    async with db.begin_nested():
        # 1. Check duplicate name within the pipeline
        name_query = select(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.name == name,
            PipelineStage.is_deleted == False
        )
        name_result = await db.execute(name_query)
        if name_result.scalars().first():
            raise PipelineStageValidationError(f"Stage with name '{name}' already exists in this pipeline")

        # 2. Check or assign order position
        if order_position is None:
            max_query = select(func.max(PipelineStage.order_position)).filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.is_deleted == False
            )
            max_result = await db.execute(max_query)
            max_pos = max_result.scalar()
            order_position = (max_pos or 0) + 1
        else:
            if order_position <= 0:
                raise PipelineStageValidationError("Order position must be positive")
            pos_query = select(PipelineStage).filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.order_position == order_position,
                PipelineStage.is_deleted == False
            )
            pos_result = await db.execute(pos_query)
            if pos_result.scalars().first():
                raise PipelineStageValidationError(f"Stage with order position {order_position} already exists")

        # 3. Handle system default swap within pipeline
        if is_system_default:
            await db.execute(
                update(PipelineStage)
                .filter(PipelineStage.pipeline_id == pipeline_id, PipelineStage.is_deleted == False)
                .values(is_system_default=False)
            )

        # 4. Create and save
        stage = PipelineStage(
            organization_id=org_id,
            pipeline_id=pipeline_id,
            name=name,
            order_position=order_position,
            color=data_dict.get("color", "#4F46E5"),
            probability=data_dict.get("probability", 0),
            is_won=data_dict.get("is_won", False),
            is_lost=data_dict.get("is_lost", False),
            is_system_default=is_system_default,
            is_active=data_dict.get("is_active", True)
        )
        db.add(stage)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await MetadataCacheService.invalidate_pipelines(org_id)
    if actor:
        await AuditService(db).log_event(
            organization_id=org_id,
            actor_user_id=actor.id,
            action="STAGE_CREATED",
            resource_type="PipelineStage",
            resource_id=str(stage.id),
            action_metadata={"name": stage.name, "pipeline_id": str(pipeline_id)}
        )
    return stage


async def reorder_stages(
    db: AsyncSession,
    org_id: uuid.UUID,
    stage_order_list: list[dict],
    actor: User | None = None
) -> list[PipelineStage]:
    if actor:
        _ensure_admin(actor)

    # Fetch all active stages of this org
    query = select(PipelineStage).filter(
        PipelineStage.organization_id == org_id,
        PipelineStage.is_deleted == False
    )
    res = await db.execute(query)
    stages = res.scalars().all()
    stages_by_id = {stage.id: stage for stage in stages}

    # Validate all stage IDs exist in org
    input_ids = set()
    for item in stage_order_list:
        stage_id_val = item.get("stage_id")
        stage_id = uuid.UUID(str(stage_id_val)) if not isinstance(stage_id_val, uuid.UUID) else stage_id_val
        new_pos = item.get("new_position")

        if new_pos is None or new_pos <= 0:
            raise PipelineStageValidationError("Position must be a positive integer")
        if stage_id not in stages_by_id:
            raise PipelineStageValidationError(f"Stage with ID {stage_id} not found in this organization")
        input_ids.add(stage_id)

    # Compute final positions and check duplicates
    final_positions = {}
    for sid, s in stages_by_id.items():
        if sid not in input_ids:
            final_positions[sid] = s.order_position

    for item in stage_order_list:
        stage_id_val = item.get("stage_id")
        stage_id = uuid.UUID(str(stage_id_val)) if not isinstance(stage_id_val, uuid.UUID) else stage_id_val
        new_pos = item.get("new_position")

        if new_pos in final_positions.values():
            raise PipelineStageValidationError(f"Duplicate order position detected: position {new_pos} is already in use")
        final_positions[stage_id] = new_pos

    if len(set(final_positions.values())) != len(final_positions):
        raise PipelineStageValidationError("Duplicate order positions detected in final ordering")

    async with db.begin_nested():
        # Shift positions to temporary negative positions to prevent unique constraint conflicts
        for item in stage_order_list:
            stage_id_val = item.get("stage_id")
            stage_id = uuid.UUID(str(stage_id_val)) if not isinstance(stage_id_val, uuid.UUID) else stage_id_val
            new_pos = item.get("new_position")
            stage = stages_by_id[stage_id]
            stage.order_position = -1000 - new_pos
            db.add(stage)
        await db.flush()

        # Apply real positions
        for item in stage_order_list:
            stage_id_val = item.get("stage_id")
            stage_id = uuid.UUID(str(stage_id_val)) if not isinstance(stage_id_val, uuid.UUID) else stage_id_val
            new_pos = item.get("new_position")
            stage = stages_by_id[stage_id]
            stage.order_position = new_pos
            db.add(stage)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await MetadataCacheService.invalidate_pipelines(org_id)
    if actor:
        await AuditService(db).log_event(
            organization_id=org_id,
            actor_user_id=actor.id,
            action="STAGE_REORDERED",
            resource_type="PipelineStage",
            resource_id=None,
            action_metadata={"reordered_count": len(stage_order_list)}
        )

    # Re-fetch stages to get the correct database order
    res = await db.execute(
        select(PipelineStage)
        .filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
        .order_by(PipelineStage.order_position)
    )
    return list(res.scalars().all())


async def delete_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    stage_id: uuid.UUID,
    fallback_stage_id: uuid.UUID | None = None,
    actor: User | None = None
) -> None:
    if actor:
        _ensure_admin(actor)

    # Fetch target stage
    stage_query = select(PipelineStage).filter(
        PipelineStage.organization_id == org_id,
        PipelineStage.id == stage_id,
        PipelineStage.is_deleted == False
    )
    stage_res = await db.execute(stage_query)
    stage = stage_res.scalar()
    if not stage:
        raise PipelineStageValidationError("Target pipeline stage not found")

    if stage.is_system_default:
        raise PipelineStageValidationError("Cannot delete the system default stage. Set another stage as default first.")

    # Check dependencies on active leads
    lead_count_query = select(func.count(Lead.id)).filter(
        Lead.organization_id == org_id,
        Lead.stage_id == stage_id,
        Lead.is_deleted == False
    )
    lead_count_res = await db.execute(lead_count_query)
    lead_count = lead_count_res.scalar() or 0

    async with db.begin_nested():
        if lead_count > 0:
            if not fallback_stage_id:
                raise PipelineStageDeletionError(
                    f"Cannot delete stage because it contains {lead_count} active lead(s). Please provide a fallback stage."
                )
            if fallback_stage_id == stage_id:
                raise PipelineStageValidationError("Fallback stage cannot be the same as the stage being deleted")

            # Validate fallback stage
            fallback_query = select(PipelineStage).filter(
                PipelineStage.organization_id == org_id,
                PipelineStage.id == fallback_stage_id,
                PipelineStage.is_deleted == False
            )
            fallback_res = await db.execute(fallback_query)
            fallback = fallback_res.scalar()
            if not fallback:
                raise PipelineStageValidationError("Fallback pipeline stage not found")

            # Move leads
            await db.execute(
                update(Lead)
                .filter(Lead.organization_id == org_id, Lead.stage_id == stage_id, Lead.is_deleted == False)
                .values(stage_id=fallback_stage_id)
            )

        # Soft-delete stage and modify unique key fields
        stage.is_deleted = True
        stage.is_active = False
        stage.deleted_at = datetime.now(timezone.utc)
        stage.name = f"{stage.name} (deleted {uuid.uuid4().hex[:8]})"
        stage.order_position = -1 * int(uuid.uuid4().int % 10000000)
        db.add(stage)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await MetadataCacheService.invalidate_pipelines(org_id)
    if actor:
        await AuditService(db).log_event(
            organization_id=org_id,
            actor_user_id=actor.id,
            action="STAGE_DELETED",
            resource_type="PipelineStage",
            resource_id=str(stage_id),
            action_metadata={"id": str(stage_id)}
        )

    from app.services.dashboard_service import DashboardService
    await DashboardService.invalidate_cache(org_id)


async def update_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    stage_id: uuid.UUID,
    data: dict | PipelineStageUpdate,
    actor: User | None = None
) -> PipelineStage:
    if actor:
        _ensure_admin(actor)

    if hasattr(data, "model_dump"):
        data_dict = data.model_dump(exclude_unset=True)
    else:
        data_dict = {k: v for k, v in dict(data).items() if v is not None}

    stage_query = select(PipelineStage).filter(
        PipelineStage.organization_id == org_id,
        PipelineStage.id == stage_id,
        PipelineStage.is_deleted == False
    )
    stage_res = await db.execute(stage_query)
    stage = stage_res.scalar()
    if not stage:
        raise PipelineStageValidationError("Pipeline stage not found")

    name = data_dict.get("name")
    order_position = data_dict.get("order_position")
    is_system_default = data_dict.get("is_system_default")
    pipeline_id = stage.pipeline_id

    async with db.begin_nested():
        if name is not None:
            name = name.strip()
            if not name:
                raise PipelineStageValidationError("Stage name cannot be empty")
            
            # Check duplicate name within the same pipeline
            name_query = select(PipelineStage).filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.name == name,
                PipelineStage.id != stage_id,
                PipelineStage.is_deleted == False
            )
            name_res = await db.execute(name_query)
            if name_res.scalars().first():
                raise PipelineStageValidationError(f"Stage with name '{name}' already exists in this pipeline")
            stage.name = name

        if order_position is not None:
            if order_position <= 0:
                raise PipelineStageValidationError("Order position must be positive")
            
            # Check duplicate position within the same pipeline
            pos_query = select(PipelineStage).filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.order_position == order_position,
                PipelineStage.id != stage_id,
                PipelineStage.is_deleted == False
            )
            pos_res = await db.execute(pos_query)
            if pos_res.scalars().first():
                raise PipelineStageValidationError(f"Stage with order position {order_position} already exists")
            stage.order_position = order_position

        if is_system_default is not None:
            if is_system_default:
                # Set all other stages in the pipeline to False
                await db.execute(
                    update(PipelineStage)
                    .filter(PipelineStage.pipeline_id == pipeline_id, PipelineStage.is_deleted == False)
                    .values(is_system_default=False)
                )
                stage.is_system_default = True
            else:
                if stage.is_system_default:
                    raise PipelineStageValidationError("Cannot unset default stage. Mark another stage as default instead.")

        if "color" in data_dict:
            stage.color = data_dict["color"]
        if "probability" in data_dict:
            stage.probability = data_dict["probability"]
        if "is_won" in data_dict:
            stage.is_won = data_dict["is_won"]
        if "is_lost" in data_dict:
            stage.is_lost = data_dict["is_lost"]
        if "is_active" in data_dict:
            stage.is_active = data_dict["is_active"]

        db.add(stage)
        await MetadataCacheService.increment_metadata_version(db, org_id)
        await db.flush()

    await MetadataCacheService.invalidate_pipelines(org_id)
    if actor:
        await AuditService(db).log_event(
            organization_id=org_id,
            actor_user_id=actor.id,
            action="STAGE_UPDATED",
            resource_type="PipelineStage",
            resource_id=str(stage_id),
            action_metadata={"name": stage.name}
        )
    return stage


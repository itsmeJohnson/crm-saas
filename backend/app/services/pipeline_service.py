import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.pipeline import PipelineStage
from app.models.lead import Lead
from app.core.exceptions import PipelineStageValidationError, PipelineStageDeletionError
from app.schemas.pipeline import PipelineStageCreate, PipelineStageUpdate

async def create_stage(db: AsyncSession, org_id: uuid.UUID, data: dict | PipelineStageCreate) -> PipelineStage:
    """
    Appends a new pipeline stage for an organization.
    If order_position isn't provided, auto-increment it to the end of the line.
    """
    if hasattr(data, "model_dump"):
        data_dict = data.model_dump()
    else:
        data_dict = dict(data)

    name = data_dict.get("name")
    order_position = data_dict.get("order_position")
    is_system_default = data_dict.get("is_system_default", False)

    if not name or not name.strip():
        raise PipelineStageValidationError("Stage name cannot be empty")
    name = name.strip()

    # 1. Check duplicate name (active only)
    name_query = select(PipelineStage).filter(
        PipelineStage.organization_id == org_id,
        PipelineStage.name == name,
        PipelineStage.is_deleted == False
    )
    name_result = await db.execute(name_query)
    if name_result.scalars().first():
        raise PipelineStageValidationError(f"Stage with name '{name}' already exists in this organization")

    # 2. Check or assign order position
    if order_position is None:
        max_query = select(func.max(PipelineStage.order_position)).filter(
            PipelineStage.organization_id == org_id,
            PipelineStage.is_deleted == False
        )
        max_result = await db.execute(max_query)
        max_pos = max_result.scalar()
        order_position = (max_pos or 0) + 1
    else:
        if order_position <= 0:
            raise PipelineStageValidationError("Order position must be positive")
        pos_query = select(PipelineStage).filter(
            PipelineStage.organization_id == org_id,
            PipelineStage.order_position == order_position,
            PipelineStage.is_deleted == False
        )
        pos_result = await db.execute(pos_query)
        if pos_result.scalars().first():
            raise PipelineStageValidationError(f"Stage with order position {order_position} already exists")

    # 3. Handle system default swap
    if is_system_default:
        await db.execute(
            update(PipelineStage)
            .filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
            .values(is_system_default=False)
        )

    # 4. Create and save
    stage = PipelineStage(
        organization_id=org_id,
        name=name,
        order_position=order_position,
        is_system_default=is_system_default
    )
    db.add(stage)
    await db.flush()
    return stage

async def reorder_stages(db: AsyncSession, org_id: uuid.UUID, stage_order_list: list[dict]) -> list[PipelineStage]:
    """
    Accepts a list of dicts [{'stage_id': uuid, 'new_position': int}] and updates
    the positions in a single transaction, validating that no duplicate positions exist.
    """
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

    # Shift positions to temporary negative positions to prevent unique constraint conflicts during bulk updates
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
    await db.flush()

    # Re-fetch stages to get the correct database order and return them sorted by position
    res = await db.execute(
        select(PipelineStage)
        .filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
        .order_by(PipelineStage.order_position)
    )
    return list(res.scalars().all())

async def delete_stage(db: AsyncSession, org_id: uuid.UUID, stage_id: uuid.UUID, fallback_stage_id: uuid.UUID | None = None) -> None:
    """
    Deletes a pipeline stage. Validates dependencies on active leads.
    """
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
    stage.deleted_at = datetime.now(timezone.utc)
    stage.name = f"{stage.name} (deleted {uuid.uuid4().hex[:8]})"
    stage.order_position = -1 * int(uuid.uuid4().int % 10000000)
    db.add(stage)
    await db.flush()

    from app.services.dashboard_service import DashboardService
    await DashboardService.invalidate_cache(org_id)

async def update_stage(db: AsyncSession, org_id: uuid.UUID, stage_id: uuid.UUID, data: dict | PipelineStageUpdate) -> PipelineStage:
    """
    Updates properties of an existing pipeline stage.
    """
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

    if name is not None:
        name = name.strip()
        if not name:
            raise PipelineStageValidationError("Stage name cannot be empty")
        
        # Check duplicate name
        name_query = select(PipelineStage).filter(
            PipelineStage.organization_id == org_id,
            PipelineStage.name == name,
            PipelineStage.id != stage_id,
            PipelineStage.is_deleted == False
        )
        name_res = await db.execute(name_query)
        if name_res.scalars().first():
            raise PipelineStageValidationError(f"Stage with name '{name}' already exists in this organization")
        stage.name = name

    if order_position is not None:
        if order_position <= 0:
            raise PipelineStageValidationError("Order position must be positive")
        
        # Check duplicate position
        pos_query = select(PipelineStage).filter(
            PipelineStage.organization_id == org_id,
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
            # Set all other stages to False
            await db.execute(
                update(PipelineStage)
                .filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
                .values(is_system_default=False)
            )
            stage.is_system_default = True
        else:
            # Cannot unset default if it is currently default and no other default exists
            if stage.is_system_default:
                raise PipelineStageValidationError("Cannot unset default stage. Mark another stage as default instead.")

    db.add(stage)
    await db.flush()
    return stage

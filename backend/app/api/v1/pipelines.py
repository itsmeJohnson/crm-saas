import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.pipeline import PipelineStage
from app.middleware.permissions import require_active_user, require_role
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineStageCreate,
    PipelineStageUpdate,
    PipelineStageReorderRequest,
    PipelineStageResponse
)
from app.services import pipeline_service
from app.core.exceptions import PipelineStageValidationError, PipelineStageDeletionError

router = APIRouter()

# ── Dynamic Pipelines Endpoints ───────────────────────────────────────────────

@router.get("/all", response_model=List[PipelineResponse])
async def list_all_pipelines(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    List all active pipelines and their nested stages for the organization.
    """
    return await pipeline_service.list_pipelines(db, actor)

@router.post("/all", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_new_pipeline(
    req: PipelineCreate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Create a new dynamic pipeline. Admin only.
    """
    try:
        pipeline = await pipeline_service.create_pipeline(db, actor, req.model_dump())
        await db.commit()
        return pipeline
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch("/all/{pipeline_id}", response_model=PipelineResponse)
async def update_existing_pipeline(
    pipeline_id: uuid.UUID,
    req: PipelineUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Update a pipeline metadata properties. Admin only.
    """
    try:
        pipeline = await pipeline_service.update_pipeline(db, actor, pipeline_id, req.model_dump(exclude_unset=True))
        await db.commit()
        return pipeline
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/all/{pipeline_id}", status_code=status.HTTP_200_OK)
async def delete_existing_pipeline(
    pipeline_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    reassignment_pipeline_id: uuid.UUID | None = Query(None)
):
    """
    Soft-delete a pipeline. Blocks if active leads refer to it unless reassignment_pipeline_id is provided.
    Admin only.
    """
    try:
        await pipeline_service.delete_pipeline(db, actor, pipeline_id, reassignment_pipeline_id)
        await db.commit()
        return {"status": "success", "message": "Pipeline and its stages successfully deleted"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ── Stage Operations (REST-Consistent Aliases) ────────────────────────────────

@router.post("/stages", response_model=PipelineStageResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_stage_rest(
    req: PipelineStageCreate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    REST-consistent endpoint to create a stage.
    """
    try:
        stage = await pipeline_service.create_stage(db, actor.organization_id, req)
        await db.commit()
        return stage
    except PipelineStageValidationError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch("/stages/{stage_id}", response_model=PipelineStageResponse)
async def update_pipeline_stage_rest(
    stage_id: uuid.UUID,
    req: PipelineStageUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    REST-consistent endpoint to update a stage.
    """
    try:
        stage = await pipeline_service.update_stage(db, actor.organization_id, stage_id, req)
        await db.commit()
        return stage
    except PipelineStageValidationError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/stages/{stage_id}", status_code=status.HTTP_200_OK)
async def delete_pipeline_stage_rest(
    stage_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    fallback_stage_id: uuid.UUID | None = Query(None)
):
    """
    REST-consistent endpoint to delete a stage.
    """
    try:
        await pipeline_service.delete_stage(db, actor.organization_id, stage_id, fallback_stage_id)
        await db.commit()
        return {"status": "deleted", "message": "Pipeline stage successfully deleted"}
    except (PipelineStageValidationError, PipelineStageDeletionError) as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/stages/reorder", response_model=List[PipelineStageResponse])
async def reorder_pipeline_stages_rest(
    req: PipelineStageReorderRequest,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    REST-consistent endpoint to reorder stages.
    """
    try:
        stage_order_list = [item.model_dump() for item in req.orders]
        stages = await pipeline_service.reorder_stages(db, actor.organization_id, stage_order_list)
        await db.commit()
        return stages
    except PipelineStageValidationError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ── Legacy Endpoints for Backward Compatibility ──────────────────────────────

@router.get("/", response_model=List[PipelineStageResponse])
async def list_pipeline_stages(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Legacy endpoint: List all active stages for the organization, ordered by position.
    """
    query = (
        select(PipelineStage)
        .filter(PipelineStage.organization_id == actor.organization_id, PipelineStage.is_deleted == False)
        .order_by(PipelineStage.order_position)
    )
    result = await db.execute(query)
    return list(result.scalars().all())

@router.post("/", response_model=PipelineStageResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_stage(
    req: PipelineStageCreate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Legacy endpoint: Create stage.
    """
    return await create_pipeline_stage_rest(req, actor, db)

@router.post("/reorder", response_model=List[PipelineStageResponse])
async def reorder_pipeline_stages(
    req: PipelineStageReorderRequest,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Legacy endpoint: Reorder stages.
    """
    return await reorder_pipeline_stages_rest(req, actor, db)

@router.patch("/{stage_id}", response_model=PipelineStageResponse)
async def update_pipeline_stage(
    stage_id: uuid.UUID,
    req: PipelineStageUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Legacy endpoint: Update stage.
    """
    return await update_pipeline_stage_rest(stage_id, req, actor, db)

@router.delete("/{stage_id}", status_code=status.HTTP_200_OK)
async def delete_pipeline_stage(
    stage_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    fallback_stage_id: uuid.UUID | None = Query(None)
):
    """
    Legacy endpoint: Delete stage.
    """
    return await delete_pipeline_stage_rest(stage_id, actor, db, fallback_stage_id)

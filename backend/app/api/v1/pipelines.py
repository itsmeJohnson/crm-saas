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
    PipelineStageCreate,
    PipelineStageUpdate,
    PipelineStageReorderRequest,
    PipelineStageResponse
)
from app.services import pipeline_service
from app.core.exceptions import PipelineStageValidationError, PipelineStageDeletionError

router = APIRouter()

@router.get("/", response_model=List[PipelineStageResponse])
async def list_pipeline_stages(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    List all active pipeline stages for the organization, ordered by order_position.
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
    Create a new pipeline stage for the organization.
    Only OrgAdmin and Manager can create stages.
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

@router.post("/reorder", response_model=List[PipelineStageResponse])
async def reorder_pipeline_stages(
    req: PipelineStageReorderRequest,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Reorder multiple pipeline stages in a single batch update.
    Only OrgAdmin and Manager can reorder stages.
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

@router.patch("/{stage_id}", response_model=PipelineStageResponse)
async def update_pipeline_stage(
    stage_id: uuid.UUID,
    req: PipelineStageUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Update a pipeline stage properties (e.g. name, position, default flag).
    Only OrgAdmin and Manager can update stages.
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

@router.delete("/{stage_id}", status_code=status.HTTP_200_OK)
async def delete_pipeline_stage(
    stage_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    fallback_stage_id: uuid.UUID | None = Query(None)
):
    """
    Delete a pipeline stage. If active leads are linked, a fallback_stage_id must be provided to move them.
    Only OrgAdmin and Manager can delete stages.
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

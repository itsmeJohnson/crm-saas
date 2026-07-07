import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.workflow_engine import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowDetail, PublishRequest, EnableRequest,
    VersionRow, RollbackRequest, ExecutionResponse, ExecutionList, WorkflowReport, WorkflowDashboard,
    ImportRequest, SimpleResult,
)
from app.services.workflow_engine_service import WorkflowEngineService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Catalog / dashboard / reports ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return WorkflowEngineService.catalog()


@router.get("/dashboard", response_model=WorkflowDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).dashboard(actor)


@router.get("/report", response_model=WorkflowReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).report(actor)


# ---------- Templates ----------
@router.post("/templates/seed", response_model=SimpleResult)
async def seed_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).seed_templates(actor)


@router.post("/templates/{workflow_id}/instantiate", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def instantiate_template(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).instantiate_template(actor, workflow_id)


# ---------- Executions ----------
@router.get("/executions", response_model=ExecutionList)
async def executions(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     workflow_id: uuid.UUID | None = Query(None), is_test: bool | None = Query(None),
                     skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await WorkflowEngineService(db).executions(actor, workflow_id=workflow_id, is_test=is_test, skip=skip, limit=limit)


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def execution_logs(execution_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).execution_logs(actor, execution_id)


@router.post("/executions/{execution_id}/rollback", response_model=dict)
async def rollback_execution(execution_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).rollback_execution(actor, execution_id)


# ---------- CRUD ----------
@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         category: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
                         is_template: bool | None = Query(None), trigger: str | None = Query(None)):
    return await WorkflowEngineService(db).list(actor, category=category, status_filter=status_filter,
                                                is_template=is_template, trigger=trigger)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(req: WorkflowCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump()
    if payload.get("graph") is not None:
        payload["graph"] = req.graph.model_dump() if req.graph else None
    return await WorkflowEngineService(db).create(actor, payload)


@router.post("/import", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def import_workflow(req: ImportRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).import_one(actor, req.model_dump())


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).get(actor, workflow_id)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: uuid.UUID, req: WorkflowUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump(exclude_unset=True)
    if "graph" in payload and req.graph is not None:
        payload["graph"] = req.graph.model_dump()
    return await WorkflowEngineService(db).update(actor, workflow_id, payload)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await WorkflowEngineService(db).delete(actor, workflow_id)


@router.get("/{workflow_id}/export")
async def export_workflow(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).export_one(actor, workflow_id)


# ---------- Lifecycle ----------
@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish(workflow_id: uuid.UUID, req: PublishRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).publish(actor, workflow_id, notes=req.notes)


@router.post("/{workflow_id}/enable", response_model=WorkflowResponse)
async def set_enabled(workflow_id: uuid.UUID, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).set_enabled(actor, workflow_id, req.enabled)


@router.post("/{workflow_id}/clone", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def clone(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).clone(actor, workflow_id)


@router.get("/{workflow_id}/versions", response_model=List[VersionRow])
async def versions(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).versions(actor, workflow_id)


@router.post("/{workflow_id}/rollback", response_model=WorkflowResponse)
async def rollback(workflow_id: uuid.UUID, req: RollbackRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).rollback(actor, workflow_id, req.version)


@router.post("/{workflow_id}/test", response_model=ExecutionResponse)
async def test_run(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await WorkflowEngineService(db).test_run(actor, workflow_id)

import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse,
    TaskCommentCreate, TaskCommentResponse,
    TaskDependencyCreate, TaskDependencyResponse,
    TaskChecklistToggle, TaskAttachmentResponse,
    TaskBulkUpdateRequest, TaskBulkDeleteRequest, TaskBulkResult, TaskReportResponse,
)
from app.services.task_service import TaskService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(req: TaskCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create a task (optionally linked to a lead/contact/company)."""
    return await TaskService(db).create_task(actor, req.model_dump())


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"), priority: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None), lead_id: uuid.UUID | None = Query(None),
    contact_id: uuid.UUID | None = Query(None), company_id: uuid.UUID | None = Query(None),
    overdue: bool | None = Query(None), due_from: datetime | None = Query(None), due_to: datetime | None = Query(None),
    search: str | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """List tasks (scoped to your own tasks unless OrgAdmin/Manager)."""
    return list(await TaskService(db).list_tasks(
        actor, status_filter=status_filter, priority=priority, assigned_user_id=assigned_user_id,
        lead_id=lead_id, contact_id=contact_id, company_id=company_id, overdue=overdue,
        due_from=due_from, due_to=due_to, search=search, skip=skip, limit=limit))


@router.get("/reports", response_model=TaskReportResponse)
async def task_reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Task analytics: open/completed/overdue, completion rate, by status/priority/assignee."""
    return await TaskService(db).get_report(actor)


@router.get("/calendar", response_model=List[TaskResponse])
async def task_calendar(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime = Query(...), date_to: datetime = Query(...),
):
    """Tasks with due dates in a range (for calendar views)."""
    return list(await TaskService(db).calendar(actor, date_from, date_to))


@router.post("/bulk-update", response_model=TaskBulkResult)
async def bulk_update_tasks(req: TaskBulkUpdateRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Bulk set status/priority/assignee on many tasks."""
    result = await TaskService(db).bulk_update(actor, req.task_ids, req.fields.model_dump(exclude_unset=True))
    return TaskBulkResult(**result)


@router.post("/bulk-delete", response_model=TaskBulkResult)
async def bulk_delete_tasks(req: TaskBulkDeleteRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await TaskService(db).bulk_delete(actor, req.task_ids)
    return TaskBulkResult(**result)


# --- Single task ---

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).get_task(actor, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: uuid.UUID, req: TaskUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).update_task(actor, task_id, req.model_dump(exclude_unset=True))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await TaskService(db).delete_task(actor, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Mark a task done (blocked if it has unfinished dependencies; spawns next occurrence if recurring)."""
    return await TaskService(db).complete_task(actor, task_id)


@router.patch("/{task_id}/checklist", response_model=TaskResponse)
async def toggle_checklist(task_id: uuid.UUID, req: TaskChecklistToggle, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Toggle a checklist item's done state."""
    return await TaskService(db).toggle_checklist(actor, task_id, req.item_id, req.done)


# --- Comments ---

@router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
async def list_comments(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await TaskService(db).list_comments(actor, task_id))


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(task_id: uuid.UUID, req: TaskCommentCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).add_comment(actor, task_id, req.body)


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(task_id: uuid.UUID, comment_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await TaskService(db).delete_comment(actor, task_id, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Attachments ---

@router.get("/{task_id}/attachments", response_model=List[TaskAttachmentResponse])
async def list_attachments(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).list_attachments(actor, task_id)


@router.post("/{task_id}/attachments", response_model=TaskAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)], file: UploadFile = File(...)):
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    return await TaskService(db).add_attachment(actor, task_id, content, file.filename or "attachment")


@router.delete("/{task_id}/attachments/{stored_name}")
async def delete_attachment(task_id: uuid.UUID, stored_name: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).delete_attachment(actor, task_id, stored_name)


# --- Dependencies ---

@router.get("/{task_id}/dependencies", response_model=List[TaskDependencyResponse])
async def list_dependencies(task_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TaskService(db).list_dependencies(actor, task_id)


@router.post("/{task_id}/dependencies", response_model=TaskDependencyResponse, status_code=status.HTTP_201_CREATED)
async def add_dependency(task_id: uuid.UUID, req: TaskDependencyCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Mark this task as blocked by another (guards against cycles)."""
    dep = await TaskService(db).add_dependency(actor, task_id, req.depends_on_task_id)
    return {"id": dep.id, "task_id": dep.task_id, "depends_on_task_id": dep.depends_on_task_id,
            "depends_on_title": None, "depends_on_status": None}


@router.delete("/{task_id}/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dependency(task_id: uuid.UUID, dependency_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await TaskService(db).delete_dependency(actor, task_id, dependency_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

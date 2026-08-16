import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.prompt_studio_service import PromptStudioService

router = APIRouter()


class PromptCreate(BaseModel):
    key: str = Field(..., max_length=60)
    name: str = Field(..., max_length=150)
    template: str
    task_type: str = "general"
    system_prompt: str | None = None
    description: str | None = None
    model_override: str | None = None
    provider_override: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    tags: list[str] = []


class PromptUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    template: str | None = None
    task_type: str | None = None
    system_prompt: str | None = None
    description: str | None = None
    model_override: str | None = None
    provider_override: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    tags: list[str] | None = None
    change_note: str | None = None


class ReviewRequest(BaseModel):
    note: str | None = None


class TestRequest(BaseModel):
    template_id: uuid.UUID | None = None
    template: str | None = None
    system_prompt: str | None = None
    task_type: str | None = None
    variables: dict = {}
    run: bool = False
    model_override: str | None = None
    provider_override: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)


def _svc(db):
    return PromptStudioService(db)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/analytics")
async def analytics(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).analytics(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.get("/categories")
async def categories(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).categories(actor)


@router.get("/library")
async def library(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).library(actor)


@router.get("/prompts")
async def list_prompts(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)],
                       task_type: str | None = Query(None), status: str | None = Query(None),
                       q: str | None = Query(None), tag: str | None = Query(None),
                       builtin: bool | None = Query(None)):
    return await _svc(db).list_prompts(actor, task_type=task_type, status_f=status, q=q,
                                       tag=tag, builtin=builtin)


@router.post("/prompts", status_code=201)
async def create_prompt(req: PromptCreate, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_prompt(actor, req.model_dump())


@router.post("/test")
async def test_prompt(req: TestRequest, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).test_prompt(actor, req.model_dump())


@router.get("/prompts/{template_id}")
async def get_prompt(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_prompt(actor, template_id)


@router.patch("/prompts/{template_id}")
async def update_prompt(template_id: uuid.UUID, req: PromptUpdate,
                        actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_prompt(actor, template_id, req.model_dump(exclude_unset=True))


@router.delete("/prompts/{template_id}")
async def delete_prompt(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).delete_prompt(actor, template_id)


@router.post("/prompts/{template_id}/duplicate", status_code=201)
async def duplicate(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).duplicate(actor, template_id)


@router.get("/prompts/{template_id}/versions")
async def versions(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).versions(actor, template_id)


@router.post("/prompts/{template_id}/versions/{version}/restore")
async def restore_version(template_id: uuid.UUID, version: int,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).restore_version(actor, template_id, version)


@router.post("/prompts/{template_id}/submit")
async def submit(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).submit(actor, template_id)


@router.post("/prompts/{template_id}/approve")
async def approve(template_id: uuid.UUID, req: ReviewRequest,
                  actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).approve(actor, template_id, req.note)


@router.post("/prompts/{template_id}/reject")
async def reject(template_id: uuid.UUID, req: ReviewRequest,
                 actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).reject(actor, template_id, req.note)


@router.post("/prompts/{template_id}/archive")
async def archive(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).archive(actor, template_id)

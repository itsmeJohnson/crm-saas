import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.workflow_assistant_service import WorkflowAssistantService

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000)
    create: bool = False
    name: str | None = Field(None, max_length=150)


def _svc(db):
    return WorkflowAssistantService(db)


@router.get("/suggestions")
async def suggestions(actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).suggestions(actor)


@router.get("/automation-suggestions")
async def automation_suggestions(actor: Annotated[User, Depends(require_active_user)],
                                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).automation_suggestions(actor)


@router.get("/rule-recommendations")
async def rule_recommendations(actor: Annotated[User, Depends(require_active_user)],
                               db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).rule_recommendations(actor)


@router.get("/bottlenecks")
async def bottlenecks(actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).bottlenecks(actor)


@router.get("/optimizations")
async def optimizations(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).optimizations(actor)


@router.post("/generate")
async def generate(req: GenerateRequest, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).generate(actor, req.prompt, create=req.create, name=req.name)


@router.get("/workflows/{workflow_id}/validate")
async def validate(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).validate(actor, workflow_id)


@router.post("/workflows/{workflow_id}/simulate")
async def simulate(workflow_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).simulate(actor, workflow_id)


@router.get("/insights")
async def insights(actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)],
                   workflow_id: uuid.UUID | None = Query(None)):
    return await _svc(db).insights(actor, workflow_id)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)

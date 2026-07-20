import uuid
from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.copilot_service import CopilotService
from app.middleware.permissions import require_active_user

router = APIRouter()


class AskRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None


class ExecuteRequest(BaseModel):
    action: dict


def _svc(db):
    return CopilotService(db)


@router.get("/capabilities")
async def capabilities(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).capabilities()


@router.post("/ask")
async def ask(req: AskRequest, actor: Annotated[User, Depends(require_active_user)],
              db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).ask(actor, req.model_dump())


@router.post("/execute")
async def execute(req: ExecuteRequest, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).execute(actor, req.action)


@router.get("/conversations")
async def conversations(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).conversations(actor)


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: uuid.UUID,
                                actor: Annotated[User, Depends(require_active_user)],
                                db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).messages(actor, conversation_id)

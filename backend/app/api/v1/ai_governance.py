from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.ai_governance_service import AIGovernanceService

router = APIRouter()


class PolicyUpdate(BaseModel):
    is_enabled: bool | None = None
    pii_detection: bool | None = None
    pii_action: str | None = None
    pii_types: list[str] | None = None
    injection_protection: bool | None = None
    injection_action: str | None = None
    content_filter: bool | None = None
    blocked_terms: list[str] | None = None
    allowed_providers: list[str] | None = None
    allowed_models: list[str] | None = None
    role_restrictions: dict | None = None
    max_prompt_chars: int | None = Field(None, ge=100, le=1000000)
    require_grounding: bool | None = None
    log_prompt_snippets: bool | None = None


class PreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


def _svc(db):
    return AIGovernanceService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.get("/policy")
async def get_policy(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    out = await svc.policy(actor)
    await db.commit()
    return out


@router.patch("/policy")
async def update_policy(req: PolicyUpdate, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_policy(actor, req.model_dump(exclude_unset=True))


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    out = await svc.dashboard(actor)
    await db.commit()
    return out


@router.get("/events")
async def events(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 limit: int = Query(100, ge=1, le=500),
                 event_type: str | None = Query(None), action: str | None = Query(None)):
    return await _svc(db).events(actor, limit=limit, event_type=event_type, action=action)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    out = await svc.report(actor)
    await db.commit()
    return out


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.post("/preview")
async def preview(req: PreviewRequest, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    out = await svc.preview(actor, req.text)
    await db.commit()
    return out

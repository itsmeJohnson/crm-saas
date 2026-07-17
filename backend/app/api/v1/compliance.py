import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.compliance_service import ComplianceService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return ComplianceService(db)


@router.get("/meta")
async def meta(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).meta()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/logs")
async def logs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
               category: str | None = Query(None), action: str | None = Query(None),
               actor_user_id: uuid.UUID | None = Query(None), resource_type: str | None = Query(None),
               q: str | None = Query(None), days: int = Query(90, ge=1, le=365),
               limit: int = Query(100, ge=1, le=300), offset: int = Query(0, ge=0)):
    return await _svc(db).logs(actor, category=category, action=action, actor_user_id=actor_user_id,
                               resource_type=resource_type, q=q, days=days, limit=limit, offset=offset)


@router.get("/login-history")
async def login_history(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)],
                        user_id: uuid.UUID | None = Query(None), days: int = Query(30, ge=1, le=365),
                        limit: int = Query(200, ge=1, le=500)):
    return await _svc(db).login_history(actor, user_id=user_id, days=days, limit=limit)


@router.get("/user-activity/{user_id}")
async def user_activity(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)], days: int = Query(30, ge=1, le=365)):
    return await _svc(db).user_activity(actor, user_id, days=days)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 days: int = Query(30, ge=1, le=365)):
    return await _svc(db).report(actor, days=days)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     category: str | None = Query(None), days: int = Query(90, ge=1, le=365)):
    return await _svc(db).export_csv(actor, category=category, days=days)

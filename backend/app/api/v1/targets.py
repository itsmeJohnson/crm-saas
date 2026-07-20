from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.target import (
    TargetRow, TargetDashboardResponse, TargetReportResponse, TargetCreateRequest, TargetCreateResult,
)
from app.services.target_service import TargetService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("/dashboard", response_model=TargetDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TargetService(db).dashboard(actor)


@router.get("/report", response_model=TargetReportResponse)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 scope: str | None = Query(None), period: str | None = Query(None)):
    return await TargetService(db).report(actor, scope=scope, period=period)


@router.get("", response_model=List[TargetRow])
async def list_targets(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                       scope: str | None = Query(None), period: str | None = Query(None),
                       status_filter: str = Query("active", alias="status")):
    return await TargetService(db).list_targets(actor, scope=scope, period=period, status_filter=status_filter)


@router.post("", response_model=TargetCreateResult, status_code=status.HTTP_201_CREATED)
async def create_target(req: TargetCreateRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TargetService(db).create_target(actor, req.model_dump())

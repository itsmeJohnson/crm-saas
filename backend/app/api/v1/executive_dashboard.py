import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.executive_dashboard import (
    CatalogResponse, DashboardResponse, DashboardRequest, ViewCreate, ViewUpdate, ViewResponse,
)
from app.services.executive_dashboard_service import ExecutiveDashboardService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return ExecutiveDashboardService(db).catalog()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    persona: str | None = Query(None), scope: str = Query("organization"),
                    date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await ExecutiveDashboardService(db).compose(
        actor, None, persona=persona, scope=scope, date_from=date_from, date_to=date_to)


@router.post("/dashboard", response_model=DashboardResponse)
async def dashboard_custom(req: DashboardRequest, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await ExecutiveDashboardService(db).compose(
        actor, req.widgets, persona=req.persona, scope=req.scope or "organization",
        date_from=_d(req.date_from), date_to=_d(req.date_to))


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     persona: str | None = Query(None), scope: str = Query("organization"),
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    csv_text = await ExecutiveDashboardService(db).export_csv(
        actor, None, persona=persona, scope=scope, date_from=date_from, date_to=date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=executive-dashboard.csv"})


# ---------- saved views ----------
@router.get("/views", response_model=List[ViewResponse])
async def list_views(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ExecutiveDashboardService(db).list_views(actor)


@router.post("/views", response_model=ViewResponse, status_code=status.HTTP_201_CREATED)
async def create_view(req: ViewCreate, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await ExecutiveDashboardService(db).create_view(actor, req.model_dump())


@router.patch("/views/{view_id}", response_model=ViewResponse)
async def update_view(view_id: uuid.UUID, req: ViewUpdate, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await ExecutiveDashboardService(db).update_view(actor, view_id, req.model_dump(exclude_unset=True))


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(view_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    await ExecutiveDashboardService(db).delete_view(actor, view_id)

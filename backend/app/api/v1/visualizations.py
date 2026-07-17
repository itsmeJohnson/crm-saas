import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.visualization import RenderRequest, DrilldownRequest, VizCreate, VizUpdate
from app.services.visualization_service import VisualizationService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return VisualizationService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.post("/render")
async def render(req: RenderRequest, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).render(actor, req.model_dump())


@router.post("/drilldown")
async def drilldown(req: DrilldownRequest, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).drilldown(actor, req.model_dump())


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


# ---------- saved visualizations ----------
@router.get("")
async def list_saved(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     viz_type: str | None = Query(None)):
    return await _svc(db).list_saved(actor, viz_type=viz_type)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(req: VizCreate, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create(actor, req.model_dump())


@router.get("/{viz_id}/data")
async def render_saved(viz_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).render_saved(actor, viz_id)


@router.get("/{viz_id}/export", response_class=PlainTextResponse)
async def export_csv(viz_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor, viz_id)


@router.patch("/{viz_id}")
async def update(viz_id: uuid.UUID, req: VizUpdate, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update(actor, viz_id, req.model_dump(exclude_unset=True))


@router.delete("/{viz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(viz_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete(actor, viz_id)

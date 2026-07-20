import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.kpi import KPICreate, KPIUpdate, KPIResponse
from app.services.kpi_service import KPIService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return KPIService(db)


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).catalog()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).report(actor)


@router.post("/evaluate")
async def evaluate_all(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).evaluate_all_for(actor)


# ---------- alerts ----------
@router.get("/alerts")
async def list_alerts(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      resolved: bool | None = Query(None), limit: int = Query(100, ge=1, le=300)):
    return await _svc(db).list_alerts(actor, resolved=resolved, limit=limit)


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).resolve_alert(actor, alert_id)


# ---------- CRUD ----------
@router.get("", response_model=List[KPIResponse])
async def list_kpis(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    category: str | None = Query(None), active_only: bool = Query(False)):
    return await _svc(db).list_kpis(actor, category=category, active_only=active_only)


@router.post("", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(req: KPICreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create(actor, req.model_dump())


@router.patch("/{kpi_id}", response_model=KPIResponse)
async def update_kpi(kpi_id: uuid.UUID, req: KPIUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update(actor, kpi_id, req.model_dump(exclude_unset=True))


@router.delete("/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kpi(kpi_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete(actor, kpi_id)


@router.get("/{kpi_id}/evaluate")
async def evaluate_kpi(kpi_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).evaluate(actor, kpi_id)

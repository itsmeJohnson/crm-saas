import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.employee_analytics import TrainingCreate, TrainingUpdate, TrainingResponse
from app.services.employee_analytics_service import EmployeeAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return EmployeeAnalyticsService(db)


@router.get("/roster")
async def roster(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).roster(actor, date_from, date_to)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/leaderboard")
async def leaderboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      metric: str = Query("leads_converted"), date_from: date | None = Query(None),
                      date_to: date | None = Query(None), limit: int = Query(20, ge=1, le=100)):
    return await _svc(db).leaderboard(actor, metric=metric, date_from=date_from, date_to=date_to, limit=limit)


@router.get("/manager-comparison")
async def manager_comparison(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                             date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).manager_comparison(actor, date_from, date_to)


@router.get("/comparison/{kind}")
async def structure_comparison(kind: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                               date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).structure_comparison(actor, kind, date_from, date_to)


@router.get("/attendance-trend")
async def attendance_trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                           user_id: uuid.UUID | None = Query(None), date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).attendance_trend(actor, user_id=user_id, date_from=date_from, date_to=date_to)


@router.get("/heatmap")
async def heatmap(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  user_id: uuid.UUID | None = Query(None), date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).heatmap(actor, user_id=user_id, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = Query(None), date_to: date | None = Query(None)):
    csv_text = await _svc(db).export_csv(actor, date_from, date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=employee-analytics.csv"})


# ---------- training ----------
@router.get("/trainings", response_model=List[TrainingResponse])
async def list_trainings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                         user_id: uuid.UUID | None = Query(None)):
    return await _svc(db).list_trainings(actor, user_id=user_id)


@router.post("/trainings", response_model=TrainingResponse, status_code=status.HTTP_201_CREATED)
async def create_training(req: TrainingCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_training(actor, req.model_dump())


@router.patch("/trainings/{training_id}", response_model=TrainingResponse)
async def update_training(training_id: uuid.UUID, req: TrainingUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_training(actor, training_id, req.model_dump(exclude_unset=True))


@router.delete("/trainings/{training_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training(training_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_training(actor, training_id)


# ---------- employee deep-dive (last: /{user_id} would shadow static paths) ----------
@router.get("/{user_id}")
async def employee(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = Query(None), date_to: date | None = Query(None)):
    return await _svc(db).employee(actor, user_id, date_from, date_to)


@router.get("/{user_id}/performance-trend")
async def performance_trend(user_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                            granularity: str = Query("weekly"), count: int = Query(8, ge=1, le=52)):
    return await _svc(db).performance_trend(actor, user_id, granularity=granularity, count=count)

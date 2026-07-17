import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.okr import (ObjectiveCreate, ObjectiveUpdate, KeyResultCreate, KeyResultUpdate,
                             CheckinRequest, ReviewCreate)
from app.services.okr_service import OKRService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return OKRService(db)


@router.get("/meta")
async def meta(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).meta()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/report")
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 level: str | None = Query(None), cycle_year: int | None = Query(None),
                 cycle_quarter: int | None = Query(None)):
    return await _svc(db).report(actor, level=level, cycle_year=cycle_year, cycle_quarter=cycle_quarter)


@router.get("/tree")
async def tree(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
               cycle_year: int | None = Query(None)):
    return await _svc(db).tree(actor, cycle_year=cycle_year)


@router.post("/scan")
async def scan(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).scan_for(actor)


# ---------- objectives ----------
@router.get("")
async def list_objectives(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          level: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
                          cycle_year: int | None = Query(None), cycle_quarter: int | None = Query(None),
                          user_id: uuid.UUID | None = Query(None)):
    return await _svc(db).list_objectives(actor, level=level, status_filter=status_filter,
                                          cycle_year=cycle_year, cycle_quarter=cycle_quarter, user_id=user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_objective(req: ObjectiveCreate, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_objective(actor, req.model_dump())


@router.get("/{objective_id}")
async def get_objective(objective_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_objective(actor, objective_id)


@router.patch("/{objective_id}")
async def update_objective(objective_id: uuid.UUID, req: ObjectiveUpdate,
                           actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_objective(actor, objective_id, req.model_dump(exclude_unset=True))


@router.delete("/{objective_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_objective(objective_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_objective(actor, objective_id)


# ---------- key results ----------
@router.post("/{objective_id}/key-results")
async def add_key_result(objective_id: uuid.UUID, req: KeyResultCreate,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).add_key_result(actor, objective_id, req.model_dump())


@router.patch("/key-results/{kr_id}")
async def update_key_result(kr_id: uuid.UUID, req: KeyResultUpdate,
                            actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_key_result(actor, kr_id, req.model_dump(exclude_unset=True))


@router.delete("/key-results/{kr_id}")
async def delete_key_result(kr_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).delete_key_result(actor, kr_id)


@router.post("/key-results/{kr_id}/checkin")
async def checkin(kr_id: uuid.UUID, req: CheckinRequest, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).checkin(actor, kr_id, req.model_dump())


# ---------- reviews & manager feedback ----------
@router.get("/{objective_id}/reviews")
async def list_reviews(objective_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_reviews(actor, objective_id)


@router.post("/{objective_id}/reviews", status_code=status.HTTP_201_CREATED)
async def add_review(objective_id: uuid.UUID, req: ReviewCreate,
                     actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).add_review(actor, objective_id, req.model_dump())

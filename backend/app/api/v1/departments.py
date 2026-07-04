import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Response, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentList, DepartmentTreeNode,
    MemberItem, MemberAssignReq, StatusReq, TargetCreate, TargetResponse, PerformanceResponse,
    DashboardResponse, AnalyticsRow, ImportResult,
)
from app.services.department_service import DepartmentService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (before /{id}) ----------
@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).dashboard(actor)


@router.get("/tree", response_model=List[DepartmentTreeNode])
async def tree(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).tree(actor)


@router.get("/analytics", response_model=List[AnalyticsRow])
async def analytics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None)):
    return await DepartmentService(db).analytics(actor, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    csv_text = await DepartmentService(db).export_csv(actor)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=departments.csv"})


@router.post("/import", response_model=ImportResult)
async def import_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     file: UploadFile = File(...)):
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds the 2MB limit")
    result = await DepartmentService(db).import_csv(actor, content)
    await db.commit()
    return result


# ---------- CRUD ----------
@router.get("", response_model=DepartmentList)
async def list_departments(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    parent_id: uuid.UUID | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
):
    return await DepartmentService(db).list(actor, search=search, status_filter=status_filter,
                                            parent_id=parent_id, skip=skip, limit=limit)


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(req: DepartmentCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).create(actor, req.model_dump())


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(department_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).get(actor, department_id)


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(department_id: uuid.UUID, req: DepartmentUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).update(actor, department_id, req.model_dump(exclude_unset=True))


@router.post("/{department_id}/status", response_model=DepartmentResponse)
async def set_status(department_id: uuid.UUID, req: StatusReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).set_status(actor, department_id, req.status)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await DepartmentService(db).delete(actor, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Members ----------
@router.get("/{department_id}/members", response_model=List[MemberItem])
async def list_members(department_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).members(actor, department_id)


@router.post("/{department_id}/members")
async def assign_members(department_id: uuid.UUID, req: MemberAssignReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await DepartmentService(db).assign_members(actor, department_id, req.user_ids)
    await db.commit()
    return result


@router.post("/{department_id}/members/remove")
async def remove_members(department_id: uuid.UUID, req: MemberAssignReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).remove_members(actor, department_id, req.user_ids)


# ---------- Targets ----------
@router.get("/{department_id}/targets", response_model=List[TargetResponse])
async def list_targets(department_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await DepartmentService(db).list_targets(actor, department_id))


@router.post("/{department_id}/targets", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(department_id: uuid.UUID, req: TargetCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await DepartmentService(db).create_target(actor, department_id, req.model_dump())


@router.delete("/{department_id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(department_id: uuid.UUID, target_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await DepartmentService(db).delete_target(actor, department_id, target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Performance / KPIs ----------
@router.get("/{department_id}/performance", response_model=PerformanceResponse)
async def performance(department_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      date_from: datetime | None = Query(None), date_to: datetime | None = Query(None)):
    return await DepartmentService(db).performance(actor, department_id, date_from=date_from, date_to=date_to)

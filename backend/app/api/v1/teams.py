import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamList, TeamMemberItem, MemberChangeRequest,
    TeamTargetCreate, TeamTargetResponse, TeamPerformanceResponse, TeamDashboardResponse,
    TeamAnalyticsRow, TeamCalendarItem, AssignWorkRequest, AssignWorkResult,
    BulkTeamRequest, BulkTeamResult, TeamImportResult, TeamReportResponse,
)
from app.services.team_service import TeamService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (before /{id}) ----------
@router.get("/dashboard", response_model=TeamDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).dashboard(actor)


@router.get("/analytics", response_model=List[TeamAnalyticsRow])
async def analytics(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: datetime | None = Query(None),
                    date_to: datetime | None = Query(None)):
    return await TeamService(db).analytics(actor, date_from=date_from, date_to=date_to)


@router.get("/report", response_model=TeamReportResponse)
async def report(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 date_from: datetime | None = Query(None),
                 date_to: datetime | None = Query(None)):
    return await TeamService(db).report(actor, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    csv_text = await TeamService(db).export_csv(actor)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=teams.csv"})


@router.post("/import", response_model=TeamImportResult)
async def import_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     file: UploadFile = File(...)):
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds the 2MB limit")
    result = await TeamService(db).import_csv(actor, content)
    await db.commit()
    return result


@router.post("/bulk", response_model=BulkTeamResult)
async def bulk_action(req: BulkTeamRequest, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).bulk_action(actor, req.team_ids, req.action)


# ---------- CRUD ----------
@router.get("", response_model=TeamList)
async def list_teams(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    department_id: uuid.UUID | None = Query(None), leader_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
):
    return await TeamService(db).list(actor, search=search, status_filter=status_filter,
                                      department_id=department_id, leader_id=leader_id,
                                      skip=skip, limit=limit)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(req: TeamCreate, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).create(actor, req.model_dump())


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).get(actor, team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(team_id: uuid.UUID, req: TeamUpdate,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).update(actor, team_id, req.model_dump(exclude_unset=True))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    await TeamService(db).delete(actor, team_id)


# ---------- Members ----------
@router.get("/{team_id}/members", response_model=List[TeamMemberItem])
async def members(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).members(actor, team_id)


@router.post("/{team_id}/members")
async def add_members(team_id: uuid.UUID, req: MemberChangeRequest,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).add_members(actor, team_id, req.user_ids)


@router.post("/{team_id}/members/remove")
async def remove_members(team_id: uuid.UUID, req: MemberChangeRequest,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).remove_members(actor, team_id, req.user_ids)


# ---------- Targets ----------
@router.get("/{team_id}/targets", response_model=List[TeamTargetResponse])
async def list_targets(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).list_targets(actor, team_id)


@router.post("/{team_id}/targets", response_model=TeamTargetResponse,
             status_code=status.HTTP_201_CREATED)
async def create_target(team_id: uuid.UUID, req: TeamTargetCreate,
                        actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await TeamService(db).create_target(actor, team_id, req.model_dump())


@router.delete("/{team_id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(team_id: uuid.UUID, target_id: uuid.UUID,
                        actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    await TeamService(db).delete_target(actor, team_id, target_id)


# ---------- Performance / calendar / assignment ----------
@router.get("/{team_id}/performance", response_model=TeamPerformanceResponse)
async def performance(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      date_from: datetime | None = Query(None),
                      date_to: datetime | None = Query(None)):
    return await TeamService(db).performance(actor, team_id, date_from=date_from, date_to=date_to)


@router.get("/{team_id}/calendar", response_model=List[TeamCalendarItem])
async def calendar(team_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: datetime = Query(...), date_to: datetime = Query(...)):
    return await TeamService(db).calendar(actor, team_id, date_from, date_to)


@router.post("/{team_id}/assign-leads", response_model=AssignWorkResult)
async def assign_leads(team_id: uuid.UUID, req: AssignWorkRequest,
                       actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    if not req.lead_ids:
        raise HTTPException(status_code=400, detail="lead_ids is required")
    return await TeamService(db).assign_leads(actor, team_id, req.lead_ids, strategy=req.strategy)


@router.post("/{team_id}/assign-tasks", response_model=AssignWorkResult)
async def assign_tasks(team_id: uuid.UUID, req: AssignWorkRequest,
                       actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    if not req.task_ids:
        raise HTTPException(status_code=400, detail="task_ids is required")
    return await TeamService(db).assign_tasks(actor, team_id, req.task_ids, strategy=req.strategy)

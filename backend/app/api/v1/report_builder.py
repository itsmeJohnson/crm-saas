import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.report_builder import (
    ReportCreate, ReportUpdate, ReportResponse, RunResult, PreviewRequest, ScheduleRequest,
    RestoreRequest, VersionRow, SimpleCreated,
)
from app.services.report_builder_service import ReportBuilderService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return ReportBuilderService(db).catalog()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).dashboard(actor)


# ---------- templates ----------
@router.get("/templates", response_model=List[ReportResponse])
async def list_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).list_templates(actor)


@router.post("/templates/seed", response_model=SimpleCreated)
async def seed_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).seed_templates(actor)


@router.post("/templates/{report_id}/instantiate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def instantiate(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).instantiate_template(actor, report_id)


# ---------- preview (run an unsaved definition) ----------
@router.post("/preview", response_model=RunResult)
async def preview(req: PreviewRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    data = req.model_dump()
    limit = data.pop("limit"); offset = data.pop("offset")
    return await ReportBuilderService(db).run_definition(actor, data, limit=limit, offset=offset)


# ---------- CRUD ----------
@router.get("", response_model=List[ReportResponse])
async def list_reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                       box: str = Query("mine"), dataset: str | None = Query(None)):
    return await ReportBuilderService(db).list_reports(actor, box=box, dataset=dataset)


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(req: ReportCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).create(actor, req.model_dump())


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).get(actor, report_id)


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(report_id: uuid.UUID, req: ReportUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).update(actor, report_id, req.model_dump(exclude_unset=True))


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await ReportBuilderService(db).delete(actor, report_id)


@router.post("/{report_id}/clone", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def clone_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).clone(actor, report_id)


@router.get("/{report_id}/run", response_model=RunResult)
async def run_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return await ReportBuilderService(db).run_saved(actor, report_id, limit=limit, offset=offset)


@router.get("/{report_id}/export", response_class=PlainTextResponse)
async def export_report(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    csv_text = await ReportBuilderService(db).export_csv(actor, report_id)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=report.csv"})


# ---------- scheduling / versioning ----------
@router.patch("/{report_id}/schedule", response_model=ReportResponse)
async def set_schedule(report_id: uuid.UUID, req: ScheduleRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump()
    payload["schedule_recipients"] = [str(x) for x in (payload.get("schedule_recipients") or [])]
    return await ReportBuilderService(db).set_schedule(actor, report_id, payload)


@router.get("/{report_id}/versions", response_model=List[VersionRow])
async def list_versions(report_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).list_versions(actor, report_id)


@router.post("/{report_id}/versions/restore", response_model=ReportResponse)
async def restore_version(report_id: uuid.UUID, req: RestoreRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ReportBuilderService(db).restore_version(actor, report_id, req.version_no)

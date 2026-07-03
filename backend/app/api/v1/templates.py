import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.template import (
    TemplateResponse, TemplateCreateReq, TemplateUpdateReq, RejectReq, PreviewReq, PreviewResp,
    TestSendReq, TestSendResp, VersionResponse, VariableInfo, TemplateReportResponse,
)
from app.services.template_service import TemplateService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Metadata (static routes before /{id}) ----------
@router.get("/variables", response_model=List[VariableInfo])
async def list_variables(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """The dynamic fields usable as {{placeholders}} in template bodies/subjects."""
    return TemplateService(db).variables()


@router.get("/categories", response_model=List[str])
async def list_categories(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TemplateService(db).categories(actor)


@router.get("/reports", response_model=TemplateReportResponse)
async def reports(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Template analytics: counts by channel/status/category, usage totals, most-used, pending approvals."""
    return await TemplateService(db).reports(actor)


# ---------- CRUD ----------
@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    channel: str | None = Query(None), category: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"), search: str | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
):
    """List templates with filters (all statuses — this is the management surface)."""
    return list(await TemplateService(db).list(actor, channel=channel, category=category,
                                               status_filter=status_filter, search=search, skip=skip, limit=limit))


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(req: TemplateCreateReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create a template (starts as a draft in the approval workflow)."""
    return await TemplateService(db).create(actor, req.model_dump())


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await TemplateService(db).get(actor, template_id)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: uuid.UUID, req: TemplateUpdateReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Edit a template — snapshots the prior version and resets an approved template to draft."""
    return await TemplateService(db).update(actor, template_id, req.model_dump(exclude_unset=True))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await TemplateService(db).delete(actor, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Approval workflow ----------
@router.post("/{template_id}/submit", response_model=TemplateResponse)
async def submit_template(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Submit a draft for approval."""
    return await TemplateService(db).submit(actor, template_id)


@router.post("/{template_id}/approve", response_model=TemplateResponse)
async def approve_template(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Approve a pending template (Manager/OrgAdmin)."""
    return await TemplateService(db).approve(actor, template_id)


@router.post("/{template_id}/reject", response_model=TemplateResponse)
async def reject_template(template_id: uuid.UUID, req: RejectReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Reject a pending template with a reason (Manager/OrgAdmin)."""
    return await TemplateService(db).reject(actor, template_id, req.reason)


# ---------- Versions ----------
@router.get("/{template_id}/versions", response_model=List[VersionResponse])
async def list_versions(template_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await TemplateService(db).versions(actor, template_id))


@router.post("/{template_id}/versions/{version}/restore", response_model=TemplateResponse)
async def restore_version(template_id: uuid.UUID, version: int, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Restore a template's content to a prior version."""
    return await TemplateService(db).restore(actor, template_id, version)


# ---------- Preview + test ----------
@router.post("/{template_id}/preview", response_model=PreviewResp)
async def preview_template(template_id: uuid.UUID, req: PreviewReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Render the template with sample data, or a real contact/lead/company if provided."""
    return await TemplateService(db).preview(actor, template_id, req.model_dump())


@router.post("/{template_id}/test", response_model=TestSendResp)
async def test_template(template_id: uuid.UUID, req: TestSendReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send a test message through the template's channel (Call scripts return a preview)."""
    return await TemplateService(db).test_send(actor, template_id, req.model_dump())

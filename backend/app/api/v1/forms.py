import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user, require_role
from app.schemas.form_definition import (
    FormDefinitionCreate, FormDefinitionUpdate, FormDefinitionResponse,
)
from app.services.form_service import FormService

router = APIRouter()
_admin = require_role(["OrgAdmin", "SuperAdmin"])


@router.get("", response_model=List[FormDefinitionResponse])
async def list_forms(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str = Query(..., description="lead | contact | <custom object key>"),
    include_inactive: bool = Query(False),
):
    """List a tenant's forms for an entity. Any active user may read (to render);
    record permissions still govern the underlying create/edit."""
    return await FormService(db).list_forms(actor, entity_type, include_inactive=include_inactive)


@router.post("", response_model=FormDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    req: FormDefinitionCreate,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str = Query(...),
):
    try:
        form = await FormService(db).create_form(actor, entity_type, req.model_dump(by_alias=True))
        await db.commit()
        return form
    except HTTPException:
        await db.rollback()
        raise


@router.get("/{form_id}", response_model=FormDefinitionResponse)
async def get_form(
    form_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await FormService(db).get_form(actor, form_id)


@router.patch("/{form_id}", response_model=FormDefinitionResponse)
async def update_form(
    form_id: uuid.UUID,
    req: FormDefinitionUpdate,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        form = await FormService(db).update_form(actor, form_id, req.model_dump(by_alias=True, exclude_unset=True))
        await db.commit()
        return form
    except HTTPException:
        await db.rollback()
        raise


@router.delete("/{form_id}", status_code=status.HTTP_200_OK)
async def delete_form(
    form_id: uuid.UUID,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await FormService(db).delete_form(actor, form_id)
        await db.commit()
        return {"status": "success"}
    except HTTPException:
        await db.rollback()
        raise

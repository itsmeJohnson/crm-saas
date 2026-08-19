import json
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user, require_role
from app.schemas.custom_object import (
    CustomObjectDefinitionCreate, CustomObjectDefinitionUpdate, CustomObjectDefinitionResponse,
    CustomObjectRecordCreate, CustomObjectRecordUpdate, CustomObjectRecordResponse,
    CustomObjectRecordListResponse,
)
from app.services.custom_object_service import CustomObjectService
from app.services.custom_object_record_service import CustomObjectRecordService

router = APIRouter()
_admin = require_role(["OrgAdmin", "SuperAdmin"])


async def _commit(db: AsyncSession):
    await db.commit()


# ── Object definitions (admin) ─────────────────────────────────────────────────

@router.get("", response_model=List[CustomObjectDefinitionResponse])
async def list_objects(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(False),
):
    return await CustomObjectService(db).list_objects(actor, include_inactive=include_inactive)


@router.post("", response_model=CustomObjectDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_object(
    req: CustomObjectDefinitionCreate,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        obj = await CustomObjectService(db).create_object(actor, req.model_dump())
        await db.commit()
        return obj
    except HTTPException:
        await db.rollback()
        raise


@router.get("/{object_key}", response_model=CustomObjectDefinitionResponse)
async def get_object(
    object_key: str,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CustomObjectService(db).get_by_key(actor, object_key)


@router.patch("/{object_id}", response_model=CustomObjectDefinitionResponse)
async def update_object(
    object_id: uuid.UUID,
    req: CustomObjectDefinitionUpdate,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        obj = await CustomObjectService(db).update_object(actor, object_id, req.model_dump(exclude_unset=True))
        await db.commit()
        return obj
    except HTTPException:
        await db.rollback()
        raise


@router.delete("/{object_id}", status_code=status.HTTP_200_OK)
async def delete_object(
    object_id: uuid.UUID,
    actor: Annotated[User, Depends(_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await CustomObjectService(db).delete_object(actor, object_id)
        await db.commit()
        return {"status": "success"}
    except HTTPException:
        await db.rollback()
        raise


# ── Records (generic CRUD + typed filter/sort/paginate) ────────────────────────

@router.get("/{object_key}/records", response_model=CustomObjectRecordListResponse)
async def list_records(
    object_key: str,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    filters: str | None = Query(None, description="JSON array of {field, op, value} filters"),
    sort: str | None = Query(None, description="field:asc|desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    parsed_filters = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="filters must be valid JSON")
    return await CustomObjectRecordService(db).list_records(
        actor, object_key, filters=parsed_filters, sort=sort, page=page, page_size=page_size
    )


@router.post("/{object_key}/records", response_model=CustomObjectRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    object_key: str,
    req: CustomObjectRecordCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        rec = await CustomObjectRecordService(db).create_record(actor, object_key, req.model_dump())
        await db.commit()
        return rec
    except HTTPException:
        await db.rollback()
        raise


@router.get("/{object_key}/records/{record_id}", response_model=CustomObjectRecordResponse)
async def get_record(
    object_key: str,
    record_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CustomObjectRecordService(db).get_record(actor, object_key, record_id)


@router.patch("/{object_key}/records/{record_id}", response_model=CustomObjectRecordResponse)
async def update_record(
    object_key: str,
    record_id: uuid.UUID,
    req: CustomObjectRecordUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        rec = await CustomObjectRecordService(db).update_record(actor, object_key, record_id, req.model_dump())
        await db.commit()
        return rec
    except HTTPException:
        await db.rollback()
        raise


@router.delete("/{object_key}/records/{record_id}", status_code=status.HTTP_200_OK)
async def delete_record(
    object_key: str,
    record_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await CustomObjectRecordService(db).delete_record(actor, object_key, record_id)
        await db.commit()
        return {"status": "success"}
    except HTTPException:
        await db.rollback()
        raise

import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.role import (
    RoleCreate, RoleUpdate, RoleResponse, RoleDetailResponse, MatrixUpdate,
    FieldPermissionsUpdate, RoleAssignRequest, RoleUserItem,
    EffectivePermissionsResponse, PermissionAuditRow,
)
from app.services.permission_service import PermissionService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Static routes (before /{id}) ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return PermissionService.catalog()


@router.get("/me", response_model=EffectivePermissionsResponse)
async def my_permissions(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).effective_permissions(actor)


@router.get("/audit", response_model=List[PermissionAuditRow])
async def permission_audit(actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)],
                           limit: int = Query(100, ge=1, le=500)):
    return await PermissionService(db).permission_audit(actor, limit=limit)


# ---------- CRUD ----------
@router.get("", response_model=List[RoleResponse])
async def list_roles(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     search: str | None = Query(None),
                     status_filter: str | None = Query(None, alias="status")):
    return await PermissionService(db).list_roles(actor, search=search, status_filter=status_filter)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(req: RoleCreate, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).create_role(actor, req.model_dump())


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(role_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).get_role_detail(actor, role_id)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: uuid.UUID, req: RoleUpdate,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).update_role(actor, role_id, req.model_dump(exclude_unset=True))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    await PermissionService(db).delete_role(actor, role_id)


# ---------- Matrix / field permissions ----------
@router.put("/{role_id}/permissions", response_model=RoleDetailResponse)
async def set_matrix(role_id: uuid.UUID, req: MatrixUpdate,
                     actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    matrix = {k: v.model_dump() for k, v in req.matrix.items()}
    return await PermissionService(db).set_matrix(actor, role_id, matrix)


@router.put("/{role_id}/field-permissions", response_model=RoleDetailResponse)
async def set_field_permissions(role_id: uuid.UUID, req: FieldPermissionsUpdate,
                                actor: Annotated[User, Depends(require_active_user)],
                                db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).set_field_permissions(
        actor, role_id, [i.model_dump() for i in req.items])


# ---------- Assignment ----------
@router.get("/{role_id}/users", response_model=List[RoleUserItem])
async def role_users(role_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).users_for_role(actor, role_id)


@router.post("/{role_id}/assign")
async def assign_role(role_id: uuid.UUID, req: RoleAssignRequest,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).assign_role(actor, role_id, req.user_ids)


@router.post("/{role_id}/unassign")
async def unassign_role(role_id: uuid.UUID, req: RoleAssignRequest,
                        actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await PermissionService(db).unassign_role(actor, role_id, req.user_ids)

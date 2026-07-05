import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.services.announcement_service import AnnouncementService
from app.middleware.permissions import require_active_user

router = APIRouter()


@router.get("", response_model=List[AnnouncementResponse])
async def list_announcements(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                             scope: str = Query("mine")):
    svc = AnnouncementService(db)
    return await (svc.list_all(actor) if scope == "all" else svc.list_for_user(actor))


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(req: AnnouncementCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AnnouncementService(db).create(actor, req.model_dump())


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(announcement_id: uuid.UUID, req: AnnouncementUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await AnnouncementService(db).update(actor, announcement_id, req.model_dump(exclude_unset=True))


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(announcement_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await AnnouncementService(db).delete(actor, announcement_id)

import uuid
from datetime import date
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.booking_service import BookingService
from app.schemas.booking import (
    BookingLinkCreate, BookingLinkUpdate, BookingLinkResponse, PublicBookRequest,
)

# Tenant router (authenticated). Public router has NO auth — visitors book here.
router = APIRouter()
public_router = APIRouter()


@router.get("/links", response_model=List[BookingLinkResponse])
async def list_booking_links(actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).list_links(actor)


@router.post("/links", response_model=BookingLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_link(req: BookingLinkCreate,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).create_link(actor, req.model_dump(exclude_unset=True))


@router.patch("/links/{link_id}", response_model=BookingLinkResponse)
async def update_booking_link(link_id: uuid.UUID, req: BookingLinkUpdate,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).update_link(actor, link_id, req.model_dump(exclude_unset=True))


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking_link(link_id: uuid.UUID,
                              actor: Annotated[User, Depends(require_active_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    await BookingService(db).delete_link(actor, link_id)


# ---------------- public (no auth) ----------------
@public_router.get("/{slug}")
async def public_booking_page(slug: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).public_get(slug)


@public_router.get("/{slug}/availability")
async def public_availability(slug: str, db: Annotated[AsyncSession, Depends(get_db)],
                              date_from: date = Query(...), date_to: date = Query(...)):
    return await BookingService(db).availability(slug, date_from, date_to)


@public_router.post("/{slug}/book", status_code=status.HTTP_201_CREATED)
async def public_book(slug: str, req: PublicBookRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    return await BookingService(db).book(slug, req.model_dump())

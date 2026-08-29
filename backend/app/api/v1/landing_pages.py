import uuid
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.landing_page_service import LandingPageService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import tenant_has_feature

# Tenant router (auth + LEAD_CAPTURE feature). Public router has NO auth.
router = APIRouter()
public_router = APIRouter()

FEATURE = "LEAD_CAPTURE"


async def _require_feature(actor: User, db: AsyncSession):
    if not await tenant_has_feature(db, actor, FEATURE):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="The Website Engine is not included in your plan.")


class LandingPageIn(BaseModel):
    name: str | None = None
    slug: str | None = None
    config: dict[str, Any] | None = None
    is_published: bool | None = None
    owner_user_id: uuid.UUID | None = None


class SubmitIn(BaseModel):
    form: dict[str, Any] = {}
    utm: dict[str, Any] = {}


# ---------- Tenant (auth) ----------
@router.get("")
async def list_pages(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await LandingPageService(db).list(actor)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_page(req: LandingPageIn, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await LandingPageService(db).create(actor, req.model_dump(exclude_unset=True))


@router.get("/{page_id}")
async def get_page(page_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await LandingPageService(db).get(actor, page_id)


@router.put("/{page_id}")
async def update_page(page_id: uuid.UUID, req: LandingPageIn, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await LandingPageService(db).update(actor, page_id, req.model_dump(exclude_unset=True))


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(page_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    await LandingPageService(db).delete(actor, page_id)


# ---------- Public (no auth) ----------
@public_router.get("/{slug}")
async def public_page(slug: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """Public config for rendering a published landing page (increments views)."""
    return await LandingPageService(db).public_get(slug)


@public_router.post("/{slug}/submit")
async def public_submit(slug: str, req: SubmitIn, http_request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Public form submission -> creates a Lead with UTM attribution."""
    return await LandingPageService(db).submit(slug, req.form or {}, req.utm or {})

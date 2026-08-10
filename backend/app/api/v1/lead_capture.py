import json
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Request, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.middleware.permissions import require_role
from app.schemas.lead_capture import (
    LeadCaptureSourceCreate, LeadCaptureSourceUpdate, LeadCaptureSourceResponse, LeadCaptureEventResponse,
)
from app.services.lead_capture_service import LeadCaptureService

router = APIRouter()
_admin = require_role(["OrgAdmin", "Manager"])


def _resp(src, request: Request) -> LeadCaptureSourceResponse:
    r = LeadCaptureSourceResponse.model_validate(src)
    r.has_secret = bool(src.secret)
    path = "meta" if src.provider == "meta_lead_ads" else "inbound"
    base = str(request.base_url).rstrip("/")
    r.webhook_url = f"{base}{settings.API_V1_STR}/lead-capture/{path}/{src.token}"
    return r


# ============ admin CRUD (OrgAdmin / Manager) ============
@router.post("/sources", response_model=LeadCaptureSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(req: LeadCaptureSourceCreate, request: Request,
                        actor: Annotated[User, Depends(_admin)], db: Annotated[AsyncSession, Depends(get_db)]):
    src = await LeadCaptureService(db).create_source(actor, req.model_dump())
    return _resp(src, request)


@router.get("/sources", response_model=List[LeadCaptureSourceResponse])
async def list_sources(request: Request, actor: Annotated[User, Depends(_admin)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return [_resp(s, request) for s in await LeadCaptureService(db).list_sources(actor)]


@router.get("/sources/{source_id}", response_model=LeadCaptureSourceResponse)
async def get_source(source_id: uuid.UUID, request: Request, actor: Annotated[User, Depends(_admin)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return _resp(await LeadCaptureService(db).get_source(actor, source_id), request)


@router.patch("/sources/{source_id}", response_model=LeadCaptureSourceResponse)
async def update_source(source_id: uuid.UUID, req: LeadCaptureSourceUpdate, request: Request,
                        actor: Annotated[User, Depends(_admin)], db: Annotated[AsyncSession, Depends(get_db)]):
    src = await LeadCaptureService(db).update_source(actor, source_id, req.model_dump(exclude_unset=True))
    return _resp(src, request)


@router.post("/sources/{source_id}/rotate-token", response_model=LeadCaptureSourceResponse)
async def rotate_token(source_id: uuid.UUID, request: Request, actor: Annotated[User, Depends(_admin)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return _resp(await LeadCaptureService(db).rotate_token(actor, source_id), request)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: uuid.UUID, actor: Annotated[User, Depends(_admin)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    await LeadCaptureService(db).delete_source(actor, source_id)


@router.get("/events", response_model=List[LeadCaptureEventResponse])
async def list_events(actor: Annotated[User, Depends(_admin)], db: Annotated[AsyncSession, Depends(get_db)],
                      source_id: uuid.UUID | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await LeadCaptureService(db).list_events(actor, source_id=source_id, limit=limit)


# ============ public webhooks (no auth — token in URL) ============
@router.get("/meta/{token}")
async def meta_verify(token: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Meta (Facebook/Instagram) Lead Ads subscription handshake."""
    from fastapi.responses import PlainTextResponse
    p = request.query_params
    challenge = await LeadCaptureService(db).verify_meta(
        token, p.get("hub.verify_token"), p.get("hub.challenge"))
    return PlainTextResponse(content=challenge)


@router.post("/meta/{token}")
async def meta_inbound(token: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Meta Lead Ads `leadgen` webhook — creates a Lead from the submission."""
    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
    sig = request.headers.get("x-hub-signature-256") or request.headers.get("x-signature")
    return await LeadCaptureService(db).ingest(token, payload, raw, sig)


@router.post("/inbound/{token}")
async def generic_inbound(token: str, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Generic inbound lead webhook (Google Ads lead forms, landing pages,
    Zapier/Make, any platform). Maps the JSON payload to a Lead."""
    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload must be a JSON object")
    sig = request.headers.get("x-signature") or request.headers.get("x-hub-signature-256")
    return await LeadCaptureService(db).ingest(token, payload, raw, sig)

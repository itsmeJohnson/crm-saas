"""Integration Hub routers.

* ``router``         — management, mounted at /api/v1/integrations with JWT +
                       `_rbac("integrations")`. Managers read; only OrgAdmin and
                       above write credentials.
* ``inbound_router`` — token-authenticated inbound webhook receiver at
                       /api/v1/integrations/inbound, mounted with NO bearer auth
                       (the BI feed / AI API precedent) so external systems can
                       post directly.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.integration_service import IntegrationService

router = APIRouter()
inbound_router = APIRouter()


class IntegrationCreate(BaseModel):
    provider: str = Field(..., max_length=40)
    name: str | None = Field(None, max_length=120)
    environment: str = "live"
    credentials: dict | None = None
    config: dict | None = None
    is_enabled: bool = True
    max_attempts: int = Field(3, ge=1, le=10)
    retry_backoff_seconds: int = Field(2, ge=0, le=60)
    timeout_seconds: int = Field(15, ge=1, le=120)


class IntegrationUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    environment: str | None = None
    credentials: dict | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    max_attempts: int | None = Field(None, ge=1, le=10)
    retry_backoff_seconds: int | None = Field(None, ge=0, le=60)
    timeout_seconds: int | None = Field(None, ge=1, le=120)
    fallback_integration_id: uuid.UUID | None = None


class CallRequest(BaseModel):
    method: str = "GET"
    path: str | None = None
    params: dict | None = None
    body: dict | None = None


def _svc(db):
    return IntegrationService(db)


# ================= catalog + dashboard =================
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return IntegrationService.catalog()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


# ================= connections =================
@router.get("")
async def list_integrations(actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)],
                            category: str | None = Query(None),
                            status_filter: str | None = Query(None, alias="status")):
    return await _svc(db).list_connections(actor, category=category, status_filter=status_filter)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_integration(req: IntegrationCreate,
                             actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create(actor, req.model_dump())


@router.post("/sync-managed")
async def sync_managed(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    """Reflect the channel modules that own their own credentials into the hub."""
    return await _svc(db).sync_managed(actor)


@router.get("/logs")
async def logs(actor: Annotated[User, Depends(require_active_user)],
               db: Annotated[AsyncSession, Depends(get_db)],
               integration_id: uuid.UUID | None = Query(None),
               status_filter: str | None = Query(None, alias="status"),
               limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).logs(actor, integration_id=integration_id,
                               status_filter=status_filter, limit=limit)


@router.get("/events")
async def events(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 integration_id: uuid.UUID | None = Query(None),
                 limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).events(actor, integration_id=integration_id, limit=limit)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.post("/health-check")
async def health_check_all(actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    svc = _svc(db)
    svc._require_manager(actor)
    return await svc.health_check_all(actor.organization_id, actor)


@router.get("/{integration_id}")
async def get_integration(integration_id: uuid.UUID,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get(actor, integration_id)


@router.patch("/{integration_id}")
async def update_integration(integration_id: uuid.UUID, req: IntegrationUpdate,
                             actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update(actor, integration_id, req.model_dump(exclude_unset=True))


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(integration_id: uuid.UUID,
                             actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete(actor, integration_id)


@router.post("/{integration_id}/health-check")
async def health_check_one(integration_id: uuid.UUID,
                           actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).health_check_one(actor, integration_id)


@router.post("/{integration_id}/call")
async def call_integration(integration_id: uuid.UUID, req: CallRequest,
                           actor: Annotated[User, Depends(require_active_user)],
                           db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).call_api(actor, integration_id, req.model_dump())


@router.post("/{integration_id}/rotate-inbound")
async def rotate_inbound(integration_id: uuid.UUID,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).rotate_inbound_secret(actor, integration_id)


# ================= inbound webhook (no bearer auth) =================
@inbound_router.post("/{token}")
async def receive_inbound(token: str, request: Request,
                          db: Annotated[AsyncSession, Depends(get_db)]):
    raw = await request.body()
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": raw.decode("utf-8", "replace")[:5000]}
    signature = (request.headers.get("x-signature")
                 or request.headers.get("x-hub-signature-256")
                 or request.headers.get("x-webhook-signature"))
    if signature and signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    return await _svc(db).receive_inbound(token, payload, signature=signature, raw_body=raw)

"""AI API & SDK routers.

Two surfaces, deliberately separated:

* ``router``        — Developer Portal management, mounted under
                      /api/v1/ai-developer with the normal JWT + "ai" RBAC.
* ``public_router`` — the key-authenticated public AI API, mounted under
                      /api/v1/ai-api with NO bearer auth (the BI feed
                      precedent). Every request is authenticated by API key,
                      scope-checked, rate limited and written to the request
                      ledger.
"""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.ai_api_service import AIApiService, CURRENT_VERSION, API_VERSIONS
from app.services.ai_gateway_service import AIGatewayService

router = APIRouter()         # management — JWT + "ai" RBAC
public_router = APIRouter()  # public developer API — API-key authenticated


# ================= schemas =================
class KeyCreate(BaseModel):
    name: str = Field(..., max_length=120)
    environment: str = "live"
    scopes: list[str] | None = None
    rate_limit_per_min: int = Field(60, ge=1, le=10000)
    daily_quota: int = Field(1000, ge=1, le=1000000)
    allowed_providers: list[str] | None = None
    allowed_models: list[str] | None = None
    allowed_ips: list[str] | None = None
    expires_in_days: int | None = Field(None, ge=1, le=3650)


class KeyUpdate(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    rate_limit_per_min: int | None = Field(None, ge=1, le=10000)
    daily_quota: int | None = Field(None, ge=1, le=1000000)
    allowed_providers: list[str] | None = None
    allowed_models: list[str] | None = None
    allowed_ips: list[str] | None = None
    expires_in_days: int | None = Field(None, ge=0, le=3650)
    is_active: bool | None = None


class WebhookCreate(BaseModel):
    name: str = Field(..., max_length=120)
    url: str = Field(..., max_length=500)
    events: list[str] | None = None
    max_attempts: int = Field(5, ge=1, le=10)
    is_active: bool = True


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = Field(None, max_length=500)
    events: list[str] | None = None
    max_attempts: int | None = Field(None, ge=1, le=10)
    is_active: bool | None = None


class PublicGenerate(BaseModel):
    prompt: str | None = None
    messages: list[dict] | None = None
    task_type: str = "general"
    template_key: str | None = None
    variables: dict | None = None
    context_type: str | None = None
    context_id: str | None = None
    conversation_id: uuid.UUID | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1, le=8192)


class PublicChat(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    title: str | None = None
    context_type: str | None = None
    context_id: str | None = None
    provider: str | None = None
    model: str | None = None


def _svc(db):
    return AIApiService(db)


# ============================================================================ #
#  Management — /api/v1/ai-developer  (JWT + "ai" RBAC)
# ============================================================================ #
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return AIApiService.catalog()


@router.get("/portal")
async def portal(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 base_url: str | None = Query(None)):
    return await _svc(db).portal(actor, base_url=base_url)


# ---------- API keys ----------
@router.get("/keys")
async def list_keys(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_keys(actor)


@router.post("/keys", status_code=status.HTTP_201_CREATED)
async def create_key(req: KeyCreate, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_key(actor, req.model_dump())


@router.patch("/keys/{key_id}")
async def update_key(key_id: uuid.UUID, req: KeyUpdate,
                     actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_key(actor, key_id, req.model_dump(exclude_unset=True))


@router.post("/keys/{key_id}/rotate")
async def rotate_key(key_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).rotate_key(actor, key_id)


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).revoke_key(actor, key_id)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(key_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_key(actor, key_id)


# ---------- webhooks ----------
@router.get("/webhooks")
async def list_webhooks(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_webhooks(actor)


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(req: WebhookCreate, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_webhook(actor, req.model_dump())


@router.patch("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: uuid.UUID, req: WebhookUpdate,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_webhook(actor, webhook_id, req.model_dump(exclude_unset=True))


@router.post("/webhooks/{webhook_id}/rotate-secret")
async def rotate_webhook_secret(webhook_id: uuid.UUID,
                                actor: Annotated[User, Depends(require_active_user)],
                                db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).rotate_webhook_secret(actor, webhook_id)


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).test_webhook(actor, webhook_id)


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_webhook(actor, webhook_id)


@router.get("/webhooks/deliveries")
async def deliveries(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     webhook_id: uuid.UUID | None = Query(None),
                     status_filter: str | None = Query(None, alias="status"),
                     limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).deliveries(actor, webhook_id=webhook_id,
                                     status_filter=status_filter, limit=limit)


@router.post("/webhooks/deliveries/{delivery_id}/replay")
async def replay_delivery(delivery_id: uuid.UUID,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).replay_delivery(actor, delivery_id)


# ---------- analytics ----------
@router.get("/analytics")
async def analytics(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)],
                    days: int = Query(30, ge=1, le=365)):
    return await _svc(db).analytics(actor, days=days)


@router.get("/requests")
async def requests_log(actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)],
                       key_id: uuid.UUID | None = Query(None),
                       limit: int = Query(100, ge=1, le=500)):
    return await _svc(db).requests_log(actor, key_id=key_id, limit=limit)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     days: int = Query(30, ge=1, le=365)):
    return await _svc(db).export_csv(actor, days=days)


# ---------- documentation / SDK / examples (JWT side, for the portal) ----------
@router.get("/docs")
async def developer_docs(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)],
                         base_url: str | None = Query(None)):
    return _svc(db).docs(base_url)


@router.get("/openapi")
async def developer_openapi(actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)],
                            base_url: str | None = Query(None)):
    return _svc(db).openapi_spec(base_url)


@router.get("/examples")
async def developer_examples(actor: Annotated[User, Depends(require_active_user)],
                             db: Annotated[AsyncSession, Depends(get_db)],
                             base_url: str | None = Query(None)):
    return _svc(db).examples(base_url)


@router.get("/sdk")
async def sdk_list(actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return AIApiService.catalog()["sdk_languages"]


@router.get("/sdk/{language}")
async def sdk_source(language: str, actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)],
                     base_url: str | None = Query(None)):
    return _svc(db).sdk(language, base_url)


@router.get("/sdk/{language}/download", response_class=PlainTextResponse)
async def sdk_download(language: str, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)],
                       base_url: str | None = Query(None)):
    pack = _svc(db).sdk(language, base_url)
    return PlainTextResponse(pack["source"], media_type="text/plain", headers={
        "Content-Disposition": f'attachment; filename="{pack["filename"]}"'})


# ============================================================================ #
#  Public developer API — /api/v1/ai-api  (API-key authenticated)
# ============================================================================ #
def _raw_key(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-api-key")


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def _authenticate(request: Request, db: AsyncSession):
    svc = _svc(db)
    key, owner = await svc.authenticate(_raw_key(request), client_ip=_client_ip(request))
    return svc, key, owner


def _base_url(request: Request) -> str:
    return str(request.url).split("?")[0].rsplit("/", 1)[0]


@public_router.get("/version")
async def public_version():
    """Unauthenticated version discovery — the entry point for any client."""
    return JSONResponse({"current_version": CURRENT_VERSION, "versions": API_VERSIONS},
                        headers={"X-API-Version": CURRENT_VERSION})


@public_router.get("/openapi.json")
async def public_openapi(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Machine-readable spec for the public surface — import it anywhere."""
    return JSONResponse(_svc(db).openapi_spec(_base_url(request)),
                        headers={"X-API-Version": CURRENT_VERSION})


@public_router.post("/generate")
async def public_generate(req: PublicGenerate, request: Request,
                          db: Annotated[AsyncSession, Depends(get_db)]):
    svc, key, owner = await _authenticate(request, db)
    try:
        out, headers = await svc.api_generate(key, owner, req.model_dump())
    except HTTPException as e:
        await svc.record_failure(key, "generate", e)
        await db.commit()
        raise
    return JSONResponse(out, headers=headers)


@public_router.post("/chat")
async def public_chat(req: PublicChat, request: Request,
                      db: Annotated[AsyncSession, Depends(get_db)]):
    svc, key, owner = await _authenticate(request, db)
    try:
        out, headers = await svc.api_chat(key, owner, req.model_dump())
    except HTTPException as e:
        await svc.record_failure(key, "chat", e)
        await db.commit()
        raise
    return JSONResponse(out, headers=headers)


@public_router.post("/stream")
async def public_stream(req: PublicGenerate, request: Request,
                        db: Annotated[AsyncSession, Depends(get_db)]):
    """SSE streaming. The request is authorised, rate limited and logged before
    the first byte leaves, so a long stream can never dodge the ledger."""
    svc, key, owner = await _authenticate(request, db)
    try:
        svc.require_scope(key, "ai:stream")
        svc.check_model_allowed(key, req.provider, req.model)
        state = await svc.enforce_rate_limit(key)
        await svc.log_request(key, "stream", provider=req.provider, model=req.model)
    except HTTPException as e:
        await svc.record_failure(key, "stream", e)
        await db.commit()
        raise
    gateway = AIGatewayService(db)
    payload = req.model_dump()

    async def sse():
        try:
            async for chunk in gateway.stream_generate(owner, **payload):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except HTTPException as e:
            yield f"data: {json.dumps({'error': str(e.detail), 'status': e.status_code})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers=svc.rate_limit_headers(state))


@public_router.get("/models")
async def public_models(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    svc, key, owner = await _authenticate(request, db)
    try:
        state = await svc.enforce_rate_limit(key)
        out = await svc.api_models(key, owner)
        await svc.log_request(key, "models", method="GET")
    except HTTPException as e:
        await svc.record_failure(key, "models", e)
        await db.commit()
        raise
    return JSONResponse(out, headers=svc.rate_limit_headers(state))


@public_router.get("/templates")
async def public_templates(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    svc, key, owner = await _authenticate(request, db)
    try:
        state = await svc.enforce_rate_limit(key)
        out = await svc.api_templates(key, owner)
        await svc.log_request(key, "templates", method="GET")
    except HTTPException as e:
        await svc.record_failure(key, "templates", e)
        await db.commit()
        raise
    return JSONResponse(out, headers=svc.rate_limit_headers(state))


@public_router.get("/usage")
async def public_usage(request: Request, db: Annotated[AsyncSession, Depends(get_db)],
                       days: int = Query(30, ge=1, le=365)):
    svc, key, owner = await _authenticate(request, db)
    try:
        out = await svc.api_usage(key, days=days)
    except HTTPException as e:
        await svc.record_failure(key, "usage", e)
        await db.commit()
        raise
    return JSONResponse(out, headers={"X-API-Version": CURRENT_VERSION})

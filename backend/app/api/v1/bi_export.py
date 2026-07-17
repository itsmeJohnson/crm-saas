import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.bi_export import (TokenCreate, TokenUpdate, SettingsUpdate, WebhookExportRequest,
                                   CloudExportRequest, SyncCreate, SyncUpdate)
from app.services.bi_export_service import BIExportService
from app.middleware.permissions import require_active_user

router = APIRouter()        # management — mounted with "analytics" RBAC
feed_router = APIRouter()   # public token-authenticated BI feed — no bearer auth


def _svc(db):
    return BIExportService(db)


# ================= management =================
@router.get("/meta")
async def meta(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _svc(db).meta()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/history")
async def history(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  kind: str | None = Query(None), limit: int = Query(100, ge=1, le=300)):
    return await _svc(db).history(actor, kind=kind, limit=limit)


@router.get("/export")
async def export_download(actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)],
                          source_type: str = Query("dataset"), source_key: str = Query(...),
                          format: str = Query("csv")):
    content, mime, filename = await _svc(db).export_download(actor, source_type, source_key, format)
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/export/webhook")
async def webhook_export(req: WebhookExportRequest, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).webhook_export(actor, req.model_dump())


@router.post("/export/cloud")
async def cloud_export(req: CloudExportRequest, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).cloud_export(actor, req.model_dump())


# ---------- settings ----------
@router.get("/settings")
async def get_settings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_settings(actor)


@router.patch("/settings")
async def update_settings(req: SettingsUpdate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_settings(actor, req.model_dump(exclude_unset=True))


# ---------- BI tokens ----------
@router.get("/tokens")
async def list_tokens(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_tokens(actor)


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
async def create_token(req: TokenCreate, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_token(actor, req.model_dump())


@router.patch("/tokens/{token_id}")
async def update_token(token_id: uuid.UUID, req: TokenUpdate,
                       actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_token(actor, token_id, req.model_dump(exclude_unset=True))


@router.post("/tokens/{token_id}/rotate")
async def rotate_token(token_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).rotate_token(actor, token_id)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(token_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_token(actor, token_id)


# ---------- data syncs ----------
@router.get("/syncs")
async def list_syncs(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_syncs(actor)


@router.post("/syncs", status_code=status.HTTP_201_CREATED)
async def create_sync(req: SyncCreate, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_sync(actor, req.model_dump())


@router.patch("/syncs/{sync_id}")
async def update_sync(sync_id: uuid.UUID, req: SyncUpdate,
                      actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_sync(actor, sync_id, req.model_dump(exclude_unset=True))


@router.delete("/syncs/{sync_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sync(sync_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_sync(actor, sync_id)


@router.post("/syncs/{sync_id}/run")
async def run_sync_now(sync_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).run_sync_now(actor, sync_id)


# ================= public BI feed (token auth — Power BI / Tableau / Looker / Metabase) =================
@feed_router.get("/{token}")
async def feed_index(token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).feed_index(token)


@feed_router.get("/{token}/dataset/{dataset}.{fmt}")
async def feed_dataset(token: str, dataset: str, fmt: str, db: Annotated[AsyncSession, Depends(get_db)],
                       created_since: str | None = Query(None)):
    content, mime, filename = await _svc(db).feed_data(token, "dataset", dataset, fmt, created_since=created_since)
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@feed_router.get("/{token}/report/{report_id}.{fmt}")
async def feed_report(token: str, report_id: uuid.UUID, fmt: str, db: Annotated[AsyncSession, Depends(get_db)],
                      created_since: str | None = Query(None)):
    content, mime, filename = await _svc(db).feed_data(token, "report", str(report_id), fmt, created_since=created_since)
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})

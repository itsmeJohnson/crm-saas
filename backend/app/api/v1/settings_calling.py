from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.permissions import require_manage_telephony
from app.models.user import User
from app.schemas.telephony_settings import TelephonyConfigResponse, TelephonyConfigUpdate
from app.services.telephony_config_service import TelephonyConfigService
from app.services.telephony.factory import get_provider

router = APIRouter()

# Every endpoint below (except the provider webhook) is gated by
# require_manage_telephony → SuperAdmin or OrgAdmin(manage_integrations) only.
# Unauthorized callers get HTTP 403 {"success": false, "message": ...}.


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


@router.get("", response_model=TelephonyConfigResponse)
async def get_calling_settings(
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = TelephonyConfigService(db)
    row = await svc.get_or_create(actor.organization_id)
    await db.commit()
    return svc.to_masked_response(row)


@router.put("", response_model=TelephonyConfigResponse)
async def update_calling_settings(
    req: TelephonyConfigUpdate, request: Request,
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip, ua = _client_meta(request)
    svc = TelephonyConfigService(db)
    row = await svc.update(actor, req, ip_address=ip, browser_info=ua)
    await db.commit()
    return svc.to_masked_response(row)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calling_settings(
    request: Request,
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip, ua = _client_meta(request)
    await TelephonyConfigService(db).clear(actor, ip_address=ip, browser_info=ua)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test")
async def test_calling(
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Validate the stored (decrypted) config against the provider. Never returns
    credentials — only a success/message."""
    cfg = await TelephonyConfigService(db).get_decrypted_config(actor.organization_id)
    if not cfg:
        return {"success": False, "message": "Telephony is not configured or not active."}
    return await get_provider(cfg).connect()


@router.post("/connect")
async def connect_calling(
    request: Request,
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Activate telephony: validate creds, then set is_active / is_connected."""
    svc = TelephonyConfigService(db)
    row = await svc.get_or_create(actor.organization_id)
    row.is_active = True
    await db.flush()
    cfg = await svc.get_decrypted_config(actor.organization_id)
    result = await get_provider(cfg).connect() if cfg else {"success": False, "message": "Not configured."}
    row.is_connected = bool(result.get("success"))
    ip, ua = _client_meta(request)
    row_after = await svc.update(actor, TelephonyConfigUpdate(is_active=True), ip_address=ip, browser_info=ua)
    await db.commit()
    return {"success": row_after.is_connected, "message": result.get("message")}


@router.post("/disconnect")
async def disconnect_calling(
    actor: Annotated[User, Depends(require_manage_telephony)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = TelephonyConfigService(db)
    row = await svc.get_or_create(actor.organization_id)
    row.is_active = False
    row.is_connected = False
    await db.commit()
    return {"success": True, "message": "Telephony disconnected."}


@router.post("/webhook")
async def calling_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """UNAUTHENTICATED provider callback. Validates the shared webhook secret from
    the org config before accepting the payload. (Event handling — recording /
    disposition auto-log — is a follow-up.)"""
    payload = await request.json()
    # The org is identified by company_id in the payload (MyOperator includes it).
    from sqlalchemy import select
    from app.models.telephony_settings import TelephonySettings
    from app.core import crypto
    company_id = str(payload.get("company_id") or payload.get("companyId") or "")
    presented = request.headers.get("x-webhook-secret") or payload.get("secret") or ""
    row = None
    if company_id:
        row = (await db.execute(
            select(TelephonySettings).where(TelephonySettings.company_id == company_id)
        )).scalars().first()
    if not row or not row.webhook_secret_enc:
        return Response(status_code=status.HTTP_202_ACCEPTED)  # accept-and-ignore (no secret configured)
    expected = crypto.decrypt(row.webhook_secret_enc)
    if presented != expected:
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    # TODO(follow-up): map call.answered/end/summary/disposition onto Activity.
    return {"success": True}

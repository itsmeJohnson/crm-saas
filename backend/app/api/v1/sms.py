import uuid
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.sms import (
    SmsSettingsResponse, SmsSettingsUpdate, SmsSendRequest, SmsItem,
    SmsBulkRequest, SmsBulkResult, SmsHistoryResponse, SmsReportResponse,
    SmsStatusWebhook, SmsInboundWebhook,
)
from app.services.sms_service import SmsService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import tenant_has_feature

router = APIRouter()

SMS_FEATURE = "SMS_MESSAGING"


async def _require_sms_feature(actor: User, db: AsyncSession):
    if not await tenant_has_feature(db, actor, SMS_FEATURE):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="SMS messaging is not included in your plan.")


# ---------- Settings ----------
@router.get("/settings", response_model=SmsSettingsResponse)
async def get_sms_settings(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Fetch (or lazily create) the org's SMS provider settings. OrgAdmin/Manager view."""
    if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view SMS settings.")
    return await SmsService(db).get_settings(actor, create=True)


@router.put("/settings", response_model=SmsSettingsResponse)
async def update_sms_settings(req: SmsSettingsUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update SMS provider credentials / sender / daily cap (OrgAdmin only)."""
    return await SmsService(db).update_settings(actor, req.model_dump(exclude_unset=True))


# ---------- Sending ----------
@router.post("/send", response_model=SmsItem, status_code=status.HTTP_201_CREATED)
async def send_sms(req: SmsSendRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send a single SMS to a number or a linked lead/contact; records delivery status."""
    await _require_sms_feature(actor, db)
    service = SmsService(db)
    act = await service.send(actor, req.model_dump())
    names = await service._names({act.assigned_user_id or act.created_by})
    return service._item(act, names)


@router.post("/send-bulk", response_model=SmsBulkResult)
async def send_bulk_sms(req: SmsBulkRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send the same message to many recipients (respects the remaining daily quota)."""
    await _require_sms_feature(actor, db)
    return await SmsService(db).send_bulk(actor, req.model_dump())


@router.post("/{activity_id}/retry", response_model=SmsItem)
async def retry_sms(activity_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Retry a failed outbound SMS."""
    await _require_sms_feature(actor, db)
    service = SmsService(db)
    act = await service.retry(actor, activity_id)
    names = await service._names({act.assigned_user_id or act.created_by})
    return service._item(act, names)


# ---------- History / reports ----------
@router.get("/messages", response_model=SmsHistoryResponse)
async def sms_messages(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    direction: str | None = Query(None), sms_status: str | None = Query(None), search: str | None = Query(None),
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    """SMS history with delivery status; scoped to own messages unless OrgAdmin/Manager."""
    return await SmsService(db).messages(actor, direction=direction, sms_status=sms_status, search=search,
                                         date_from=date_from, date_to=date_to, skip=skip, limit=limit)


@router.get("/reports", response_model=SmsReportResponse)
async def sms_reports(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None), date_to: datetime | None = Query(None),
):
    """SMS analytics: sent/delivered/failed/inbound, delivery rate, segments, by status/direction/day."""
    return await SmsService(db).reports(actor, date_from=date_from, date_to=date_to)


# ---------- Webhooks (token-secured; no auth dependency) ----------
@router.post("/webhook/status", status_code=status.HTTP_200_OK)
async def sms_status_webhook(payload: SmsStatusWebhook, db: Annotated[AsyncSession, Depends(get_db)]):
    """Provider delivery-status callback. Authenticated by the per-org webhook token."""
    return await SmsService(db).handle_status(payload.token, payload.provider_message_id, payload.status, payload.error)


@router.post("/webhook/inbound", status_code=status.HTTP_200_OK)
async def sms_inbound_webhook(payload: SmsInboundWebhook, db: Annotated[AsyncSession, Depends(get_db)]):
    """Inbound SMS callback. Authenticated by the per-org webhook token; matches a
    lead/contact by phone, records the message, notifies the owner, fires workflow."""
    return await SmsService(db).handle_inbound(payload.token, payload.from_number, payload.to_number or "",
                                               payload.body, payload.provider_message_id)

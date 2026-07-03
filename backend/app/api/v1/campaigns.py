import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignResponse, CampaignCreate, CampaignUpdate, AudiencePreviewReq, AudiencePreviewResp,
    BuildReq, ScheduleReq, CampaignReport, RecipientList, CampaignDashboard,
    SegmentResponse, SegmentCreate, SegmentUpdate,
)
from app.services.campaign_service import CampaignService
from app.middleware.permissions import require_active_user
from app.dependencies.feature_guard import tenant_has_feature

router = APIRouter()

CAMPAIGN_FEATURE = "CAMPAIGN_MANAGEMENT"


async def _require_feature(actor: User, db: AsyncSession):
    if not await tenant_has_feature(db, actor, CAMPAIGN_FEATURE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Campaign management is not included in your plan.")


# ---------- Static routes first ----------
@router.get("/dashboard", response_model=CampaignDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).dashboard(actor)


@router.post("/audience/preview", response_model=AudiencePreviewResp)
async def preview_audience(req: AudiencePreviewReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Count (and sample) the audience a definition/segment resolves to on a channel."""
    return await CampaignService(db).preview_audience(actor, req.model_dump())


# ---------- Segments ----------
@router.get("/segments", response_model=List[SegmentResponse])
async def list_segments(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await CampaignService(db).list_segments(actor))


@router.post("/segments", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(req: SegmentCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).create_segment(actor, req.model_dump())


@router.patch("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(segment_id: uuid.UUID, req: SegmentUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).update_segment(actor, segment_id, req.model_dump(exclude_unset=True))


@router.delete("/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(segment_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CampaignService(db).delete_segment(actor, segment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Campaign CRUD ----------
@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"), channel: str | None = Query(None),
    search: str | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    return list(await CampaignService(db).list(actor, status_filter=status_filter, channel=channel,
                                               search=search, skip=skip, limit=limit))


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(req: CampaignCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await CampaignService(db).create(actor, req.model_dump())


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).get(actor, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: uuid.UUID, req: CampaignUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).update(actor, campaign_id, req.model_dump(exclude_unset=True))


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CampaignService(db).delete(actor, campaign_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Audience / lifecycle ----------
@router.post("/{campaign_id}/build", response_model=CampaignResponse)
async def build_audience(campaign_id: uuid.UUID, req: BuildReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Materialise the recipient queue from the campaign's audience definition."""
    return await CampaignService(db).build_audience(actor, campaign_id, req.ids)


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(campaign_id: uuid.UUID, req: ScheduleReq, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await CampaignService(db).schedule(actor, campaign_id, req.scheduled_at)


@router.post("/{campaign_id}/launch", response_model=CampaignResponse)
async def launch_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Start sending now (Call campaigns just open the agent queue)."""
    await _require_feature(actor, db)
    return await CampaignService(db).launch(actor, campaign_id)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).pause(actor, campaign_id)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _require_feature(actor, db)
    return await CampaignService(db).resume(actor, campaign_id)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).cancel(actor, campaign_id)


@router.post("/{campaign_id}/retry", response_model=CampaignResponse)
async def retry_campaign(campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Re-send failed recipients that still have retries left."""
    await _require_feature(actor, db)
    return await CampaignService(db).retry_failed(actor, campaign_id)


# ---------- Recipients / reports ----------
@router.get("/{campaign_id}/recipients", response_model=RecipientList)
async def list_recipients(
    campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
):
    return await CampaignService(db).recipients(actor, campaign_id, status_filter=status_filter, skip=skip, limit=limit)


@router.get("/{campaign_id}/reports", response_model=CampaignReport)
async def campaign_reports(
    campaign_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
    sync: bool = Query(True),
):
    """Delivery / open / click / conversion metrics + ROI (recomputed from activities by default)."""
    return await CampaignService(db).reports(actor, campaign_id, sync=sync)

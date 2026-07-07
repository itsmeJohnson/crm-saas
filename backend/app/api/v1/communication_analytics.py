from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.models.user import User
from app.schemas.communication_analytics import (
    OverviewResponse, ChannelBreakdown, AgentPerformance, ResponseTime, TalkTime,
    MissedResponse, ConversionResponse, EngagementItem, HeatmapResponse, Bucket,
)
from app.services.communication_analytics_service import CommunicationAnalyticsService
from app.services.campaign_service import CampaignService
from app.schemas.campaign import CampaignDashboard
from app.middleware.permissions import require_active_user


def _filters(
    channel: str | None = Query(None),
    direction: str | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> dict:
    return {"channel": channel, "direction": direction, "agent_id": agent_id,
            "date_from": date_from, "date_to": date_to}


router = APIRouter()
Filters = Annotated[dict, Depends(_filters)]


@router.get("/overview", response_model=OverviewResponse)
async def overview(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Cross-channel totals: volume by channel/direction, delivery + failure."""
    return await CommunicationAnalyticsService(db).overview(actor, **f)


@router.get("/by-channel", response_model=List[ChannelBreakdown])
async def by_channel(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationAnalyticsService(db).by_channel(actor, **f)


@router.get("/agents", response_model=List[AgentPerformance])
async def agents(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Per-agent cross-channel performance incl. avg talk + response time."""
    return await CommunicationAnalyticsService(db).agents(actor, **f)


@router.get("/response-time", response_model=ResponseTime)
async def response_time(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationAnalyticsService(db).response_time(actor, **f)


@router.get("/talk-time", response_model=TalkTime)
async def talk_time(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationAnalyticsService(db).talk_time(actor, **f)


@router.get("/missed", response_model=MissedResponse)
async def missed(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationAnalyticsService(db).missed(actor, **f)


@router.get("/conversion", response_model=ConversionResponse)
async def conversion(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Conversion of comm-touched leads (converted / contacted) + attributed revenue."""
    return await CommunicationAnalyticsService(db).conversion(actor, **f)


@router.get("/engagement", response_model=List[EngagementItem])
async def engagement(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     limit: int = Query(10, ge=1, le=50)):
    """Most-engaged customers/leads by interaction count."""
    return await CommunicationAnalyticsService(db).engagement(actor, limit=limit, **f)


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Communication volume by weekday × hour."""
    return await CommunicationAnalyticsService(db).heatmap(actor, **f)


@router.get("/trend", response_model=List[Bucket])
async def trend(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CommunicationAnalyticsService(db).trend(actor, **f)


@router.get("/campaigns", response_model=CampaignDashboard)
async def campaign_analytics(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CampaignService(db).dashboard(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(f: Filters, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """CSV export of the filtered communication activity log."""
    csv_text = await CommunicationAnalyticsService(db).export_csv(actor, **f)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=communication-analytics.csv"})

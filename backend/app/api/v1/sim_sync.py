import uuid
import secrets
import logging
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.pipeline import PipelineStage
from app.middleware.permissions import require_active_user
from app.services.workflow_service import WorkflowService
from app.core.redis import redis_client

router = APIRouter()
logger = logging.getLogger(__name__)

# Schema
class SimTokenCreateRequest(BaseModel):
    device_name: str = Field("Android Telecaller Mobile", max_length=100)
    device_uuid: str = Field(..., max_length=120)
    sim_carrier: Optional[str] = Field(None, max_length=50)

class SimTokenResponse(BaseModel):
    token: str
    device_name: str
    device_uuid: str
    user_id: str
    organization_id: str
    created_at: str

class SimCallLogItem(BaseModel):
    phone: str = Field(..., max_length=50)
    direction: str = Field("OUTBOUND", description="OUTBOUND | INBOUND | MISSED | REJECTED")
    duration: int = Field(0, description="Call duration in seconds")
    timestamp: Optional[datetime] = None
    sim_slot: Optional[int] = Field(1, description="SIM 1 or SIM 2")
    sim_carrier: Optional[str] = None
    call_status: Optional[str] = Field("Completed", max_length=50)
    notes: Optional[str] = None

class SimSyncBatchRequest(BaseModel):
    device_uuid: str
    logs: List[SimCallLogItem] = Field(..., min_length=1)

class SimSyncBatchResponse(BaseModel):
    success: bool
    processed_count: int
    matched_leads: int
    created_activities: int
    timestamp: str

# Helper to validate service token
async def _get_user_from_sim_token(token: str, db: AsyncSession) -> Optional[User]:
    if not token:
        return None
    # Lookup token in redis: sim_token:{token} -> json {user_id, org_id, device_uuid}
    import json
    data_str = await redis_client.get(f"sim_token:{token}")
    if not data_str:
        return None
    try:
        data = json.loads(data_str)
        user_uuid = uuid.UUID(data["user_id"])
        res = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True, User.is_deleted == False))
        return res.scalar_one_or_none()
    except Exception as e:
        logger.warning("Failed to resolve SIM token: %s", e)
        return None

@router.post("/tokens", response_model=SimTokenResponse)
async def generate_sim_token(
    payload: SimTokenCreateRequest,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generate a background service sync token for the Android Telecaller GSM sync app."""
    import json
    raw_token = f"sim_{secrets.token_urlsafe(32)}"
    now_iso = datetime.now(timezone.utc).isoformat()
    meta = {
        "user_id": str(actor.id),
        "organization_id": str(actor.organization_id),
        "device_name": payload.device_name,
        "device_uuid": payload.device_uuid,
        "sim_carrier": payload.sim_carrier or "Unknown Carrier",
        "created_at": now_iso
    }
    # Persist in Redis with 180 days expiration
    await redis_client.set(f"sim_token:{raw_token}", json.dumps(meta), ex=86400 * 180)
    # Also record under user's registered devices set
    await redis_client.sadd(f"user:{actor.id}:sim_tokens", raw_token)

    return SimTokenResponse(
        token=raw_token,
        device_name=payload.device_name,
        device_uuid=payload.device_uuid,
        user_id=str(actor.id),
        organization_id=str(actor.organization_id),
        created_at=now_iso
    )

@router.post("/sync", response_model=SimSyncBatchResponse)
async def sync_sim_call_logs(
    payload: SimSyncBatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_sim_token: Optional[str] = Header(None, alias="X-Sim-Token"),
    authorization: Optional[str] = Header(None)
):
    """Background ingestion endpoint for native Android SIM GSM call logs.
    Reads native phone call duration, caller/receiver numbers, direction directly into CRM database.
    """
    token = x_sim_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing SIM background service token in X-Sim-Token header."
        )

    actor = await _get_user_from_sim_token(token, db)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired SIM service token."
        )

    processed = 0
    matched_count = 0
    created_activities = 0

    for item in payload.logs:
        raw_digits = "".join(filter(str.isdigit, item.phone or ""))
        if not raw_digits:
            continue
        last_10 = raw_digits[-10:] if len(raw_digits) >= 10 else raw_digits

        # 1. Match lead within organization
        lead_query = select(Lead).filter(
            Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False,
            Lead.phone.like(f"%{last_10}%")
        )
        res = await db.execute(lead_query)
        lead = res.scalars().first()

        if lead:
            matched_count += 1
        else:
            # Auto-provision prospective inbound/outbound SIM lead
            stage_res = await db.execute(
                select(PipelineStage.id).where(PipelineStage.organization_id == actor.organization_id).order_by(PipelineStage.order_position.asc()).limit(1)
            )
            stage_id = stage_res.scalar_one_or_none()
            lead = Lead(
                organization_id=actor.organization_id,
                first_name="SIM Contact",
                last_name=f"({last_10})",
                title=f"Call ({item.direction}) via Android SIM",
                phone=item.phone,
                source="Android SIM Sync",
                status="Contacted" if item.duration > 0 else "New",
                assigned_user_id=actor.id,
                stage_id=stage_id,
                created_by=actor.id
            )
            db.add(lead)
            await db.flush()

        call_time = item.timestamp or datetime.now(timezone.utc)
        call_sid = f"sim-{payload.device_uuid[:8]}-{uuid.uuid4().hex[:12]}"

        direction_clean = item.direction.upper()
        if direction_clean not in ("INBOUND", "OUTBOUND", "MISSED", "REJECTED"):
            direction_clean = "OUTBOUND"

        activity = Activity(
            organization_id=actor.organization_id,
            activity_type="Call",
            subject=f"GSM SIM {direction_clean} Call ({item.duration}s)",
            description=f"Auto-synchronized from Android SIM (Slot {item.sim_slot or 1}). Notes: {item.notes or 'None'}",
            status="Completed" if item.duration > 0 else "Planned",
            assigned_user_id=actor.id,
            lead_id=lead.id,
            created_by=actor.id,
            call_sid=call_sid,
            call_direction=direction_clean,
            call_duration=item.duration,
            created_at=call_time
        )
        db.add(activity)
        created_activities += 1
        processed += 1

        # Run workflow rule
        try:
            await WorkflowService(db).run("call_logged", lead, actor)
        except Exception as e:
            logger.warning("Workflow execution failed for SIM log: %s", e)

    await db.commit()

    # Update device heartbeat
    await redis_client.set(
        f"sim_device:{payload.device_uuid}:last_sync",
        datetime.now(timezone.utc).isoformat(),
        ex=86400 * 30
    )

    return SimSyncBatchResponse(
        success=True,
        processed_count=processed,
        matched_leads=matched_count,
        created_activities=created_activities,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@router.get("/devices")
async def list_sim_devices(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List active Android Mobile SIM synchronization tokens and their sync heartbeats."""
    import json
    token_keys = await redis_client.smembers(f"user:{actor.id}:sim_tokens")
    devices = []
    for raw_key in token_keys:
        token_str = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        data_str = await redis_client.get(f"sim_token:{token_str}")
        if data_str:
            try:
                meta = json.loads(data_str)
                dev_uuid = meta.get("device_uuid")
                last_sync = await redis_client.get(f"sim_device:{dev_uuid}:last_sync")
                devices.append({
                    "token_preview": f"{token_str[:8]}••••{token_str[-4:]}",
                    "device_name": meta.get("device_name"),
                    "device_uuid": dev_uuid,
                    "sim_carrier": meta.get("sim_carrier"),
                    "created_at": meta.get("created_at"),
                    "last_sync": last_sync.decode() if isinstance(last_sync, bytes) else (last_sync or "Never")
                })
            except Exception:
                pass
    return {"devices": devices, "total": len(devices)}

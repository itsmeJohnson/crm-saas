import logging
import uuid
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.user import User
from app.schemas.telephony import CallRecordingWebhook, InboundCallWebhook
from app.schemas.activity import ActivityResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        # Maps user_id (str) to WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user: {user_id}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user: {user_id}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WS message to {user_id}: {str(e)}")
                self.disconnect(user_id)

    async def broadcast_to_organization(self, message: dict, org_id: uuid.UUID, db: AsyncSession):
        # Find all online users belonging to this organization
        query = select(User.id).filter(User.organization_id == org_id, User.is_active == True)
        res = await db.execute(query)
        user_ids = [str(uid) for uid in res.scalars().all()]
        
        for uid in user_ids:
            if uid in self.active_connections:
                await self.send_personal_message(message, uid)

ws_manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        ws_manager.disconnect(user_id)

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telephony_recording_webhook(
    payload: CallRecordingWebhook,
    db: AsyncSession = Depends(get_db)
):
    """
    Receives completed call details from the telephony provider.
    Updates corresponding activity record matching call_sid.
    """
    logger.info(f"Received telephony recording webhook for call_sid={payload.call_sid}")
    
    # 1. Look up activity by call_sid
    query = select(Activity).filter(Activity.call_sid == payload.call_sid)
    res = await db.execute(query)
    activity = res.scalars().first()
    
    if activity:
        activity.recording_url = payload.recording_url
        activity.call_duration = payload.duration
        activity.status = "Completed"
        db.add(activity)
        await db.commit()
        logger.info(f"Updated call recording for activity_id={activity.id}")
        return {"status": "updated", "activity_id": str(activity.id)}
    
    # 2. Fallback: If activity not found (e.g. direct outbound without pre-creation), log a new one.
    # We don't have lead ID from payload, but we could try to look up lead later or log it globally.
    logger.warning(f"No existing activity found matching call_sid={payload.call_sid}")
    return {"status": "ignored", "reason": "No matching call_sid"}

@router.post("/inbound", status_code=status.HTTP_200_OK)
async def inbound_call_trigger(
    payload: InboundCallWebhook,
    db: AsyncSession = Depends(get_db)
):
    """
    Receives notification of an incoming call to virtual number.
    Looks up matching lead by telephone number and sends real-time alert via WebSockets.
    """
    logger.info(f"Inbound call received: caller={payload.from_number} -> DID={payload.to_number}")
    
    # Clean caller number to match database (e.g., matching last 10 digits to handle country prefixes)
    caller_clean = payload.from_number.strip()
    last_10 = caller_clean[-10:] if len(caller_clean) >= 10 else caller_clean
    
    # Query lead table
    query = select(Lead).filter(
        Lead.is_deleted == False,
        Lead.phone.like(f"%{last_10}%")
    )
    res = await db.execute(query)
    leads = res.scalars().all()
    
    if not leads:
        logger.info(f"No matching lead found for caller: {payload.from_number}")
        return {"status": "no_match", "caller": payload.from_number}
    
    # Find matching lead
    lead = leads[0]
    org_id = lead.organization_id
    
    # Pre-create an activity representing the inbound call in progress
    # Let's check who created or is assigned to this lead
    assigned_user_id = lead.assigned_user_id
    created_by_user_id = lead.created_by
    
    new_call_activity = Activity(
        organization_id=org_id,
        activity_type="Call",
        subject=f"Inbound Call from {lead.first_name or ''} {lead.last_name or ''}".strip(),
        description=f"Inbound call initiated via virtual number {payload.to_number}.",
        status="Planned",
        assigned_user_id=assigned_user_id,
        lead_id=lead.id,
        created_by=assigned_user_id or created_by_user_id,
        call_sid=payload.call_sid,
        call_direction="INBOUND"
    )
    db.add(new_call_activity)
    await db.commit()
    await db.refresh(new_call_activity)
    
    # Broadcast alert payload via WebSockets
    alert_payload = {
        "event": "inbound_call",
        "call_sid": payload.call_sid,
        "lead_id": str(lead.id),
        "lead_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unknown Lead",
        "company_name": lead.company_name or "",
        "phone": lead.phone,
        "activity_id": str(new_call_activity.id)
    }
    
    if assigned_user_id:
        # Direct alert to assigned agent
        await ws_manager.send_personal_message(alert_payload, str(assigned_user_id))
    else:
        # Broadcast to entire tenant organization
        await ws_manager.broadcast_to_organization(alert_payload, org_id, db)
        
    return {"status": "matched", "lead_id": str(lead.id), "activity_id": str(new_call_activity.id)}

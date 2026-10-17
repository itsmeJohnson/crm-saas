import logging
import re
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, Response
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.user import User
from app.models.telephony_settings import TelephonySettings
from app.models.pipeline import PipelineStage
from app.schemas.telephony import CallRecordingWebhook, InboundCallWebhook

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
        query = select(User.id).filter(User.organization_id == org_id, User.is_active == True)
        res = await db.execute(query)
        user_ids = [str(uid) for uid in res.scalars().all()]
        
        for uid in user_ids:
            if uid in self.active_connections:
                await self.send_personal_message(message, uid)

ws_manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        await websocket.accept()
        await websocket.close(code=1008, reason="Invalid User ID format")
        return

    res = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True, User.is_deleted == False))
    user = res.scalar_one_or_none()
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="User not active")
        return

    from app.dependencies.feature_guard import tenant_has_feature
    if not await tenant_has_feature(db, user, "INBOUND_CALLING"):
        await websocket.accept()
        await websocket.close(code=1008, reason="Inbound calling feature not available")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        ws_manager.disconnect(user_id)


async def _extract_webhook_data(request: Request) -> dict:
    """Extract parameters from query string, JSON body, or form data."""
    data = {}
    if request.query_params:
        data.update(dict(request.query_params))

    if request.method.upper() == "POST":
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                json_data = await request.json()
                if isinstance(json_data, dict):
                    data.update(json_data)
            except Exception:
                pass
        else:
            try:
                form_data = await request.form()
                data.update(dict(form_data))
            except Exception:
                try:
                    json_data = await request.json()
                    if isinstance(json_data, dict):
                        data.update(json_data)
                except Exception:
                    pass
    return data


async def _handle_incoming_call_event(
    *,
    db: AsyncSession,
    caller_phone: str,
    destination_number: str,
    call_sid: str,
    agent_phone: Optional[str] = None,
    call_status: str = "Ringing",
    recording_url: Optional[str] = None,
    duration: int = 0,
) -> dict:
    """Handle an inbound call from customer to virtual number / DID."""
    digits = re.sub(r"\D", "", caller_phone or "")
    last_10 = digits[-10:] if len(digits) >= 10 else digits

    if not last_10:
        return {"status": "ignored", "reason": "No valid caller phone"}

    # 1. Search for existing lead matching the phone
    query = select(Lead).filter(
        Lead.is_deleted == False,
        Lead.phone.like(f"%{last_10}%")
    )
    res = await db.execute(query)
    leads = res.scalars().all()
    lead = leads[0] if leads else None

    # 2. If no lead found, identify tenant organization and auto-create prospective lead
    if not lead:
        dest_digits = re.sub(r"\D", "", destination_number or "")
        dest_last_10 = dest_digits[-10:] if len(dest_digits) >= 10 else dest_digits

        matched_org_id = None
        if dest_last_10:
            org_res = await db.execute(
                select(TelephonySettings.organization_id).where(
                    TelephonySettings.default_caller_id.like(f"%{dest_last_10}%")
                )
            )
            matched_org_id = org_res.scalars().first()

        if not matched_org_id:
            # Fallback to the first active tenant organization
            first_org_res = await db.execute(select(User.organization_id).filter(User.is_active == True).limit(1))
            matched_org_id = first_org_res.scalars().first()

        if matched_org_id:
            # Query default stage & admin user
            stage_res = await db.execute(
                select(PipelineStage.id).where(PipelineStage.organization_id == matched_org_id).order_by(PipelineStage.order_position.asc()).limit(1)
            )
            stage_id = stage_res.scalar_one_or_none()

            admin_user_res = await db.execute(
                select(User.id).where(User.organization_id == matched_org_id, User.is_active == True).limit(1)
            )
            admin_user_id = admin_user_res.scalar_one_or_none()

            if stage_id and admin_user_id:
                lead = Lead(
                    organization_id=matched_org_id,
                    first_name="Inbound",
                    last_name=f"Caller ({last_10})",
                    title=f"Inbound Call from {caller_phone}",
                    phone=caller_phone,
                    source="Inbound Call",
                    status="New",
                    stage_id=stage_id,
                    created_by=admin_user_id,
                )
                db.add(lead)
                await db.flush()
                logger.info(f"Auto-created prospective Lead id={lead.id} for inbound caller {caller_phone}")

    if not lead:
        logger.info(f"Inbound call: no lead found or created for caller={caller_phone}")
        return {"status": "unmatched", "caller": caller_phone}

    org_id = lead.organization_id
    assigned_user_id = lead.assigned_user_id
    created_by_user_id = lead.created_by

    # 3. Check if an activity already exists for this call_sid
    act_query = select(Activity).filter(Activity.call_sid == call_sid)
    act_res = await db.execute(act_query)
    activity = act_res.scalars().first()

    if not activity:
        activity = Activity(
            organization_id=org_id,
            activity_type="Call",
            subject=f"Inbound Call from {lead.first_name or ''} {lead.last_name or ''}".strip(),
            description=f"Inbound call via virtual number {destination_number}. Status: {call_status}",
            status="Completed" if recording_url else "Planned",
            assigned_user_id=assigned_user_id,
            lead_id=lead.id,
            created_by=assigned_user_id or created_by_user_id,
            call_sid=call_sid,
            call_direction="INBOUND",
            recording_url=recording_url,
            call_duration=duration,
        )
        db.add(activity)

        workflow_actor_id = assigned_user_id or created_by_user_id
        if workflow_actor_id:
            actor_res = await db.execute(select(User).filter(User.id == workflow_actor_id))
            workflow_actor = actor_res.scalars().first()
            if workflow_actor:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(db).run("call_logged", lead, workflow_actor)
    else:
        if recording_url:
            activity.recording_url = recording_url
        if duration:
            activity.call_duration = duration
        activity.status = "Completed" if recording_url else activity.status
        db.add(activity)

    await db.commit()
    await db.refresh(activity)

    # 4. Broadcast real-time incoming call popup alert via WebSockets
    alert_payload = {
        "event": "inbound_call",
        "call_sid": call_sid,
        "lead_id": str(lead.id),
        "lead_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unknown Lead",
        "company_name": lead.company_name or "",
        "phone": lead.phone,
        "activity_id": str(activity.id),
        "status": call_status,
        "virtual_number": destination_number,
    }

    if assigned_user_id:
        await ws_manager.send_personal_message(alert_payload, str(assigned_user_id))
    # Always broadcast to organization so active telecallers see incoming ring
    await ws_manager.broadcast_to_organization(alert_payload, org_id, db)

    return {
        "status": "matched",
        "lead_id": str(lead.id),
        "activity_id": str(activity.id),
        "event": "inbound_call"
    }


async def _handle_outbound_call_report(
    *,
    db: AsyncSession,
    call_sid: str,
    recording_url: Optional[str] = None,
    duration: int = 0,
    status_label: str = "Completed"
) -> dict:
    """Update completed outbound call activity matching call_sid."""
    query = select(Activity).filter(Activity.call_sid == str(call_sid))
    res = await db.execute(query)
    activity = res.scalars().first()

    if activity:
        if recording_url:
            activity.recording_url = recording_url
        activity.call_duration = duration
        activity.status = "Completed"
        db.add(activity)
        await db.commit()
        logger.info(f"Updated call recording for activity_id={activity.id}, call_sid={call_sid}")
        return {"status": "updated", "activity_id": str(activity.id)}

    logger.warning(f"No existing activity found matching call_sid={call_sid}")
    return {"status": "ignored", "reason": "No matching call_sid"}


async def _process_unified_telephony_webhook(request: Request, db: AsyncSession) -> dict:
    """Universal webhook processor for Callerdesk, Exotel, Knowlarity, MyOperator & custom VoIP."""
    data = await _extract_webhook_data(request)
    logger.info("Telephony webhook received [%s %s]: %s", request.method, request.url.path, data)

    # 1. Normalize field aliases across providers (Callerdesk, Exotel, generic)
    call_sid = (
        data.get("CallSid")
        or data.get("call_sid")
        or data.get("Uniqueid")
        or data.get("sid_id")
        or data.get("campid")
        or data.get("call_id")
        or f"call-{uuid.uuid4()}"
    )
    direction = str(data.get("Direction") or data.get("direction") or "").upper()
    source_number = (
        data.get("SourceNumber")
        or data.get("from_number")
        or data.get("From")
        or data.get("msisdn")
        or data.get("caller_num")
        or ""
    )
    dest_number = (
        data.get("DestinationNumber")
        or data.get("to_number")
        or data.get("To")
        or data.get("deskphone")
        or data.get("did_no")
        or ""
    )
    agent_number = (
        data.get("DialWhomNumber")
        or data.get("agent_number")
        or data.get("member_num")
        or ""
    )
    recording_url = (
        data.get("CallRecordingUrl")
        or data.get("recording_url")
        or data.get("RecordingUrl")
        or data.get("file")
        or ""
    )
    raw_duration = (
        data.get("CallDuration")
        or data.get("TalkDuration")
        or data.get("duration")
        or "0"
    )
    try:
        duration = int(float(raw_duration))
    except (ValueError, TypeError):
        duration = 0

    call_status = str(data.get("Status") or data.get("status") or data.get("callstatus") or "ANSWER")

    # 2. Determine Call Flow: Inbound vs Outbound
    is_inbound = (
        direction in ("IVR", "INBOUND")
        or (source_number and not direction and not recording_url)
    )

    if is_inbound:
        # Inbound Call Flow (Live ringing notification or inbound call report)
        return await _handle_incoming_call_event(
            db=db,
            caller_phone=str(source_number),
            destination_number=str(dest_number),
            call_sid=str(call_sid),
            agent_phone=str(agent_number),
            call_status=call_status,
            recording_url=recording_url or None,
            duration=duration,
        )
    else:
        # Outbound Call Report / Recording Update Flow
        return await _handle_outbound_call_report(
            db=db,
            call_sid=str(call_sid),
            recording_url=recording_url or None,
            duration=duration,
            status_label=call_status,
        )


@router.api_route("/webhook", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def telephony_general_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """General telephony webhook endpoint supporting both GET & POST.
    Handles Callerdesk, Exotel, Knowlarity, MyOperator Call Reports & Inbound events.
    """
    return await _process_unified_telephony_webhook(request, db)


@router.api_route("/callerdesk/webhook", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def callerdesk_specific_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Dedicated Callerdesk webhook endpoint (https://api.callerdesk.io/)
    for Live Call and Call Report integrations.
    """
    return await _process_unified_telephony_webhook(request, db)


@router.api_route("/inbound", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def inbound_call_trigger(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Inbound call trigger endpoint supporting both GET & POST payloads."""
    return await _process_unified_telephony_webhook(request, db)
